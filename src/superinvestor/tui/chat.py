from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TYPE_CHECKING

from superinvestor.agents.tools import TOOL_SCHEMAS
from superinvestor.models.agent import AgentEvent
from superinvestor.models.enums import EventKind
from superinvestor.tui.commands import dispatch, parse_command

if TYPE_CHECKING:
    from superinvestor.agents.providers.anthropic import AnthropicProvider
    from superinvestor.mcp.client import McpManager

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are superinvestor, an AI investment research assistant. "
    "You have access to market data, SEC filings, economic indicators, "
    "and superinvestor 13F tracking tools. Help the user analyze stocks, "
    "build investment theses, and make informed decisions. "
    "Be concise and data-driven in your responses."
)


class ChatSession:
    """Manages multi-turn conversation state with the AI provider.

    Routes slash commands to the command registry and free-text messages
    to the Anthropic streaming API, combining domain tools with any
    connected MCP server tools.
    """

    def __init__(
        self,
        provider: AnthropicProvider,
        mcp_manager: McpManager,
    ) -> None:
        self._provider = provider
        self._mcp = mcp_manager
        self._messages: list[dict[str, Any]] = []
        self._last_analysis_text: str = ""

    @property
    def last_analysis_text(self) -> str:
        return self._last_analysis_text

    def clear(self) -> None:
        """Reset conversation history."""
        self._messages.clear()
        self._last_analysis_text = ""

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Combine domain tools with MCP tools."""
        schemas = list(TOOL_SCHEMAS)
        schemas.extend(self._mcp.get_tool_schemas())
        return schemas

    async def _dispatch_tool(self, name: str, args: dict[str, Any]) -> str:
        """Route tool calls to either the domain tools or an MCP server."""
        if self._mcp.has_tool(name):
            return await self._mcp.call_tool(name, args)
        # Domain tools are dispatched by the provider's default handler (via
        # tool_dispatch=None).  We only reach here when called explicitly, so
        # fall through to the provider's internal dispatch.
        return await self._provider._tools.dispatch(name, args)  # pyright: ignore[reportPrivateUsage]

    async def send(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send user text and yield response events.

        If *text* starts with ``/``, it is dispatched as a command.
        Otherwise it is sent to the AI as a conversational message.
        """
        parsed = parse_command(text)
        if parsed is not None:
            async for event in self._handle_command(parsed[0], parsed[1], text):
                yield event
            return

        # Free-text chat — append user message and stream AI response.
        self._messages.append({"role": "user", "content": text})

        accumulated = ""
        async for event in self._provider.stream_messages(
            system_prompt=_SYSTEM_PROMPT,
            messages=self._messages,
            agent_name="assistant",
            tools=self._get_tool_schemas(),
            tool_dispatch=self._dispatch_tool,
        ):
            if event.kind == EventKind.TEXT_DELTA:
                accumulated += event.content
            yield event

        self._last_analysis_text = accumulated

    async def _handle_command(
        self,
        command_name: str,
        args_string: str,
        raw_text: str,
    ) -> AsyncIterator[AgentEvent]:
        """Dispatch a slash command and yield appropriate events."""
        # Import here to avoid circular import at module level.
        from superinvestor.tui.app import SuperInvestorApp

        app: SuperInvestorApp = self._app  # type: ignore[attr-defined]
        result = await dispatch(app, command_name, args_string)

        # Special-case streaming commands that the session handles itself.
        if result.stream:
            if command_name == "analyze":
                async for event in self._stream_analyze(args_string.strip().upper()):
                    yield event
                return
            if command_name == "save":
                async for event in self._stream_save(args_string.strip().upper()):
                    yield event
                return
            if command_name == "mcp" and args_string.strip().startswith("add"):
                async for event in self._stream_mcp_add(args_string):
                    yield event
                return

        # Non-streaming command — emit the result as a system message.
        if result.text:
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content=result.text,
            )
        yield AgentEvent(kind=EventKind.DONE, agent_name="system", content="")

    async def _stream_analyze(self, ticker: str) -> AsyncIterator[AgentEvent]:
        """Run the multi-agent analysis pipeline with streaming."""
        from superinvestor.engine.pipeline import stream_analysis

        accumulated = ""
        async for event in stream_analysis(self._provider, [ticker]):
            if event.kind == EventKind.TEXT_DELTA:
                accumulated += event.content
            yield event

        self._last_analysis_text = accumulated

    async def _stream_save(self, ticker: str) -> AsyncIterator[AgentEvent]:
        """Extract an investment thesis from the last analysis and save it."""
        from superinvestor.models.thesis import InvestmentThesis
        from superinvestor.store.thesis_store import ThesisStore
        from superinvestor.tui.app import SuperInvestorApp

        app: SuperInvestorApp = self._app  # type: ignore[attr-defined]

        if not self._last_analysis_text:
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content="No recent analysis to save. Run /analyze first.",
            )
            yield AgentEvent(kind=EventKind.DONE, agent_name="system", content="")
            return

        yield AgentEvent(
            kind=EventKind.TEXT_DELTA,
            agent_name="system",
            content="Extracting thesis from analysis...",
        )

        # Use a short AI call to extract structured thesis data.
        extraction_prompt = (
            f"Extract a structured investment thesis from this analysis.\n\n"
            f"Analysis:\n{self._last_analysis_text[:4000]}\n\n"
            f"Return ONLY a JSON object with these fields:\n"
            f'  "ticker": string (stock ticker),\n'
            f'  "title": string (short thesis title),\n'
            f'  "bull_case": string (1-2 sentences),\n'
            f'  "bear_case": string (1-2 sentences),\n'
            f'  "catalysts": [strings],\n'
            f'  "risks": [strings],\n'
            f'  "target_price": number or null,\n'
            f'  "confidence_score": number 0-1\n'
        )

        # Stream the extraction call.
        extraction_messages: list[dict[str, Any]] = [
            {"role": "user", "content": extraction_prompt},
        ]
        extracted = ""
        async for event in self._provider.stream_messages(
            system_prompt="You extract structured data from text. Return only valid JSON.",
            messages=extraction_messages,
            agent_name="system",
            tools=[],
        ):
            if event.kind == EventKind.TEXT_DELTA:
                extracted += event.content

        # Parse the JSON and save.
        try:
            # Strip markdown code fences if present.
            clean = extracted.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            data = json.loads(clean)
            thesis_ticker = ticker or data.get("ticker", "UNKNOWN")
            thesis = InvestmentThesis(
                ticker=thesis_ticker.upper(),
                title=data.get("title", "Untitled Thesis"),
                bull_case=data.get("bull_case", ""),
                bear_case=data.get("bear_case", ""),
                catalysts=data.get("catalysts", []),
                risks=data.get("risks", []),
                target_price=data.get("target_price"),
                confidence_score=data.get("confidence_score", 0.5),
            )

            if app.db_conn is not None:
                await ThesisStore(app.db_conn).insert(thesis)
                yield AgentEvent(
                    kind=EventKind.TEXT_DELTA,
                    agent_name="system",
                    content=f"\nSaved thesis: {thesis.title} ({thesis.ticker}, "
                    f"confidence {thesis.confidence_score:.0%})",
                )
            else:
                yield AgentEvent(
                    kind=EventKind.TEXT_DELTA,
                    agent_name="system",
                    content="\nDatabase not available.",
                )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to parse thesis extraction: %s", exc)
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content=f"\nFailed to extract thesis: {exc}",
            )

        yield AgentEvent(kind=EventKind.DONE, agent_name="system", content="")

    async def _stream_mcp_add(self, args: str) -> AsyncIterator[AgentEvent]:
        """Connect to an MCP server."""
        parts = args.strip().split()
        # args format: "add <name> <command> [extra args...]"
        if len(parts) < 3:
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content="Usage: /mcp add <name> <command> [args...]",
            )
            yield AgentEvent(kind=EventKind.DONE, agent_name="system", content="")
            return

        name = parts[1]
        command = parts[2]
        extra_args = parts[3:] if len(parts) > 3 else []

        yield AgentEvent(
            kind=EventKind.TEXT_DELTA,
            agent_name="system",
            content=f"Connecting to MCP server '{name}' ({command})...",
        )

        try:
            tools = await self._mcp.add_server(name, command, extra_args)
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content=f"\nConnected. {len(tools)} tools discovered: {', '.join(tools)}",
            )
        except Exception as exc:
            yield AgentEvent(
                kind=EventKind.TEXT_DELTA,
                agent_name="system",
                content=f"\nFailed to connect: {exc}",
            )

        yield AgentEvent(kind=EventKind.DONE, agent_name="system", content="")

    def bind_app(self, app: object) -> None:
        """Bind a reference to the app for command dispatch."""
        self._app = app
