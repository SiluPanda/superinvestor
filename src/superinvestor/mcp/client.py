from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@dataclass
class _ServerConnection:
    """Holds a live MCP server session and its discovered tools."""

    name: str
    session: ClientSession
    tools: list[Any]  # mcp Tool objects
    exit_stack: contextlib.AsyncExitStack


class McpManager:
    """Aggregates tools from multiple stdio-based MCP servers.

    Each server is launched as a subprocess and kept alive for the lifetime
    of the manager (or until explicitly removed).  Tool names are prefixed
    with the server name to avoid collisions across servers.
    """

    def __init__(self) -> None:
        self._servers: dict[str, _ServerConnection] = {}

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def add_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> list[str]:
        """Launch an MCP server and discover its tools.

        Returns the list of discovered tool names (without the server prefix).
        """
        if name in self._servers:
            logger.warning("Server %r already registered — removing first", name)
            await self.remove_server(name)

        params = StdioServerParameters(command=command, args=args or [], env=env)
        stack = contextlib.AsyncExitStack()

        try:
            transport = await stack.enter_async_context(stdio_client(params))
            read_stream, write_stream = transport
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()

            result = await session.list_tools()
            tools = list(result.tools)
        except Exception:
            logger.exception("Failed to connect to MCP server %r", name)
            await stack.aclose()
            raise

        self._servers[name] = _ServerConnection(
            name=name,
            session=session,
            tools=tools,
            exit_stack=stack,
        )
        tool_names = [t.name for t in tools]
        logger.info("Connected to MCP server %r — %d tools: %s", name, len(tools), tool_names)
        return tool_names

    async def remove_server(self, name: str) -> bool:
        """Disconnect and remove a server.  Returns True if it existed."""
        conn = self._servers.pop(name, None)
        if conn is None:
            return False
        await conn.exit_stack.aclose()
        logger.info("Removed MCP server %r", name)
        return True

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    def list_servers(self) -> list[tuple[str, list[str]]]:
        """Return ``(server_name, [tool_names])`` for every connected server."""
        return [(name, [t.name for t in conn.tools]) for name, conn in self._servers.items()]

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return Anthropic-API-formatted tool schemas for all servers.

        Tool names are prefixed as ``{server_name}__{tool_name}`` so that
        the originating server can be identified when a tool call comes back.
        """
        schemas: list[dict[str, Any]] = []
        for server_name, conn in self._servers.items():
            for tool in conn.tools:
                schemas.append(
                    {
                        "name": f"{server_name}__{tool.name}",
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema,
                    }
                )
        return schemas

    def has_tool(self, name: str) -> bool:
        """Return True if the prefixed *name* matches a registered tool."""
        parts = name.split("__", 1)
        if len(parts) != 2:
            return False
        server_name, tool_name = parts
        conn = self._servers.get(server_name)
        if conn is None:
            return False
        return any(t.name == tool_name for t in conn.tools)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a tool by its prefixed name and return the text result.

        Raises ``ValueError`` if the server or tool is not found.
        """
        parts = name.split("__", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid prefixed tool name: {name!r}")

        server_name, tool_name = parts
        conn = self._servers.get(server_name)
        if conn is None:
            raise ValueError(f"No MCP server named {server_name!r}")

        result = await conn.session.call_tool(tool_name, arguments=arguments)

        # Join text content blocks into a single string.
        text_parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                text_parts.append(text)
        return "\n".join(text_parts)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Shut down all server connections."""
        for name in list(self._servers):
            await self.remove_server(name)
