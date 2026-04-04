from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anthropic

from superinvestor.agents.tools import TOOL_SCHEMAS, DomainTools
from superinvestor.models.agent import AgentEvent, TaskRequest, TaskResult
from superinvestor.models.enums import EventKind

logger = logging.getLogger(__name__)

_MAX_TOKENS = 8192
_MAX_TOOL_ROUNDS = 25


class AnthropicProvider:
    """Agent provider backed by the Anthropic Messages API with tool use.

    Implements the ``AgentProvider`` protocol.  Handles the full tool-use
    loop: the model is called repeatedly until it produces a final
    ``end_turn`` response (or the safety cap on rounds is hit).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: DomainTools,
        base_url: str = "",
    ) -> None:
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**client_kwargs)
        self._model = model
        self._tools = tools

    # ------------------------------------------------------------------
    # Public API — protocol methods
    # ------------------------------------------------------------------

    async def run(self, task: TaskRequest) -> TaskResult:
        """Run a single agent turn with the tool use loop until completion."""
        return await self.run_with_system(
            system_prompt="You are a helpful investment research assistant.",
            user_prompt=task.prompt,
        )

    async def stream(self, task: TaskRequest) -> AsyncIterator[AgentEvent]:
        """Stream agent events using the Anthropic streaming API."""
        async for event in self.stream_with_system(
            system_prompt="You are a helpful investment research assistant.",
            user_prompt=task.prompt,
        ):
            yield event

    # ------------------------------------------------------------------
    # Extended API — used by the pipeline for role-based prompts
    # ------------------------------------------------------------------

    async def run_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        agent_name: str = "analyst",
        tools: list[dict[str, Any]] | None = None,
    ) -> TaskResult:
        """Run with an explicit system prompt (used by the pipeline for analyst roles).

        Parameters
        ----------
        system_prompt:
            The system prompt that sets the agent persona.
        user_prompt:
            The user message to send.
        agent_name:
            Label recorded on the returned ``TaskResult``.
        tools:
            Tool schemas to provide.  Defaults to ``TOOL_SCHEMAS``.
            Pass an empty list to disable tool use (e.g. for the synthesizer).
        """
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_prompt},
        ]
        reasoning_steps: list[str] = []

        response = await self._create(
            system=system_prompt,
            messages=messages,
            tools=tool_schemas,
        )

        rounds = 0
        while response.stop_reason == "tool_use" and rounds < _MAX_TOOL_ROUNDS:
            rounds += 1

            # Append the assistant turn (contains text + tool_use blocks).
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call and build tool_result blocks.
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    reasoning_steps.append(f"Called {block.name}({_summarise_args(block.input)})")
                    result = await self._tools.dispatch(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

            response = await self._create(
                system=system_prompt,
                messages=messages,
                tools=tool_schemas,
            )

        if rounds >= _MAX_TOOL_ROUNDS:
            logger.warning(
                "Agent %s hit tool-round cap (%d rounds)",
                agent_name,
                _MAX_TOOL_ROUNDS,
            )

        final_text = _extract_text(response)
        reasoning_steps.append("Produced final analysis")

        return TaskResult(
            summary=final_text,
            agent_name=agent_name,
            reasoning_steps=reasoning_steps,
            signals=_extract_signals(final_text),
        )

    async def stream_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        agent_name: str = "analyst",
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events with an explicit system prompt.

        Yields ``AgentEvent`` instances for each text delta, tool call, and
        tool result.  The tool-use loop is handled internally — after the
        model requests tools the results are fed back and streaming resumes.
        """
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_prompt},
        ]

        rounds = 0
        while rounds <= _MAX_TOOL_ROUNDS:
            rounds += 1

            accumulated_text = ""
            tool_use_blocks: list[dict[str, Any]] = []
            current_tool: dict[str, Any] | None = None
            stop_reason: str | None = None
            response_content: list[Any] = []

            async with self._client.messages.stream(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                tools=tool_schemas or anthropic.NOT_GIVEN,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool = {
                                "id": block.id,
                                "name": block.name,
                                "input_json": "",
                            }
                            yield AgentEvent(
                                kind=EventKind.TOOL_CALL,
                                agent_name=agent_name,
                                content=block.name,
                                tool_name=block.name,
                            )

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            accumulated_text += delta.text
                            yield AgentEvent(
                                kind=EventKind.TEXT_DELTA,
                                agent_name=agent_name,
                                content=delta.text,
                            )
                        elif delta.type == "input_json_delta":
                            if current_tool is not None:
                                current_tool["input_json"] += delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool is not None:
                            tool_use_blocks.append(current_tool)
                            current_tool = None

                # Get the full response for message history.
                final_message = stream.get_final_message()
                stop_reason = final_message.stop_reason
                response_content = list(final_message.content)

            # If we are done (no more tool calls), emit DONE and return.
            if stop_reason != "tool_use":
                yield AgentEvent(
                    kind=EventKind.DONE,
                    agent_name=agent_name,
                    content="",
                )
                return

            # Otherwise, execute tool calls and loop.
            messages.append({"role": "assistant", "content": response_content})

            tool_results: list[dict[str, Any]] = []
            for block in response_content:
                if block.type == "tool_use":
                    result = await self._tools.dispatch(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
                    yield AgentEvent(
                        kind=EventKind.TOOL_RESULT,
                        agent_name=agent_name,
                        content=result[:500],  # Truncate for event display
                        tool_name=block.name,
                    )

            messages.append({"role": "user", "content": tool_results})

        # Safety cap reached.
        yield AgentEvent(
            kind=EventKind.ERROR,
            agent_name=agent_name,
            content=f"Tool-use loop exceeded {_MAX_TOOL_ROUNDS} rounds",
        )

    async def stream_messages(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        *,
        agent_name: str = "assistant",
        tools: list[dict[str, Any]] | None = None,
        tool_dispatch: Callable[[str, dict[str, Any]], Awaitable[str]] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events using a caller-owned message list.

        Unlike ``stream_with_system``, this method does **not** create the
        initial user message — the caller is responsible for populating
        ``messages`` before calling.  The assistant's response (and any
        tool-result turns) are appended to ``messages`` **in-place** so the
        caller can continue the conversation across multiple turns.

        Parameters
        ----------
        system_prompt:
            The system prompt that sets the agent persona.
        messages:
            The conversation history.  Modified in-place — assistant and
            tool-result turns are appended as the stream progresses.
        agent_name:
            Label recorded on yielded ``AgentEvent`` instances.
        tools:
            Tool schemas to provide.  Defaults to ``TOOL_SCHEMAS``.
            Pass an empty list to disable tool use.
        tool_dispatch:
            Optional callable ``(name, input) -> result`` for routing tool
            calls.  When *None*, falls back to ``self._tools.dispatch``.
            This allows the caller (e.g. a chat session with MCP) to
            intercept tool calls and route them externally.
        """
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        dispatch = tool_dispatch if tool_dispatch is not None else self._tools.dispatch

        rounds = 0
        while rounds <= _MAX_TOOL_ROUNDS:
            rounds += 1

            accumulated_text = ""
            tool_use_blocks: list[dict[str, Any]] = []
            current_tool: dict[str, Any] | None = None
            stop_reason: str | None = None
            response_content: list[Any] = []

            async with self._client.messages.stream(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                tools=tool_schemas or anthropic.NOT_GIVEN,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool = {
                                "id": block.id,
                                "name": block.name,
                                "input_json": "",
                            }
                            yield AgentEvent(
                                kind=EventKind.TOOL_CALL,
                                agent_name=agent_name,
                                content=block.name,
                                tool_name=block.name,
                            )

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            accumulated_text += delta.text
                            yield AgentEvent(
                                kind=EventKind.TEXT_DELTA,
                                agent_name=agent_name,
                                content=delta.text,
                            )
                        elif delta.type == "input_json_delta":
                            if current_tool is not None:
                                current_tool["input_json"] += delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool is not None:
                            tool_use_blocks.append(current_tool)
                            current_tool = None

                # Get the full response for message history.
                final_message = stream.get_final_message()
                stop_reason = final_message.stop_reason
                response_content = list(final_message.content)

            # Append the assistant turn to the caller's message list.
            messages.append({"role": "assistant", "content": response_content})

            # If we are done (no more tool calls), emit DONE and return.
            if stop_reason != "tool_use":
                yield AgentEvent(
                    kind=EventKind.DONE,
                    agent_name=agent_name,
                    content="",
                )
                return

            # Otherwise, execute tool calls and loop.
            tool_results: list[dict[str, Any]] = []
            for block in response_content:
                if block.type == "tool_use":
                    result = await dispatch(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
                    yield AgentEvent(
                        kind=EventKind.TOOL_RESULT,
                        agent_name=agent_name,
                        content=result[:500],  # Truncate for event display
                        tool_name=block.name,
                    )

            messages.append({"role": "user", "content": tool_results})

        # Safety cap reached.
        yield AgentEvent(
            kind=EventKind.ERROR,
            agent_name=agent_name,
            content=f"Tool-use loop exceeded {_MAX_TOOL_ROUNDS} rounds",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> anthropic.types.Message:
        """Wrapper around ``messages.create`` with sensible defaults."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return await self._client.messages.create(**kwargs)


# ------------------------------------------------------------------
# Module-private helpers
# ------------------------------------------------------------------


def _extract_text(response: anthropic.types.Message) -> str:
    """Pull all text from a Messages API response."""
    parts: list[str] = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


def _summarise_args(args: dict[str, Any]) -> str:
    """Produce a short summary of tool arguments for reasoning steps."""
    parts = [f"{k}={v!r}" for k, v in args.items()]
    summary = ", ".join(parts)
    if len(summary) > 120:
        return summary[:117] + "..."
    return summary


def _extract_signals(text: str) -> list[str]:
    """Extract signal-like statements from the final analysis text.

    Looks for lines that begin with common signal indicators such as
    "Bullish:", "Bearish:", "Buy", "Sell", "Signal:", etc.
    """
    signals: list[str] = []
    pattern = re.compile(
        r"^\s*[-*]?\s*\*{0,2}((?:Bullish|Bearish|Buy|Sell|Signal|Strong Buy|Strong Sell|Neutral)[:\s].*)",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in pattern.finditer(text):
        signal = match.group(1).strip().rstrip("*")
        if signal:
            signals.append(signal)
    return signals
