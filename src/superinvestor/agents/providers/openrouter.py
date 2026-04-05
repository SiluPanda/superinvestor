from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import openai

from superinvestor.agents.tools import TOOL_SCHEMAS, DomainTools
from superinvestor.models.agent import AgentEvent, TaskRequest, TaskResult
from superinvestor.models.enums import EventKind

logger = logging.getLogger(__name__)

_MAX_TOKENS = 8192
_MAX_TOOL_ROUNDS = 25
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider:
    """Agent provider backed by OpenRouter (OpenAI-compatible API) with tool use.

    Implements the same public interface as ``AnthropicProvider`` so it can
    be used as a drop-in replacement.  Handles the full tool-use loop:
    the model is called repeatedly until it produces a final response
    (or the safety cap on rounds is hit).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: DomainTools,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
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
        """Stream agent events using the OpenAI-compatible streaming API."""
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
        """Run with an explicit system prompt (used by the pipeline for analyst roles)."""
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        openai_tools = _to_openai_tools(tool_schemas)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        reasoning_steps: list[str] = []

        response = await self._create(messages=messages, tools=openai_tools)

        rounds = 0
        while (
            response.choices[0].finish_reason == "tool_calls"
            and rounds < _MAX_TOOL_ROUNDS
        ):
            rounds += 1
            msg = response.choices[0].message

            # Append the assistant turn.
            messages.append(_message_to_dict(msg))

            # Execute each tool call and append results.
            for tc in msg.tool_calls or []:
                args = json.loads(tc.function.arguments)
                reasoning_steps.append(
                    f"Called {tc.function.name}({_summarise_args(args)})"
                )
                result = await self._tools.dispatch(tc.function.name, args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

            response = await self._create(messages=messages, tools=openai_tools)

        if rounds >= _MAX_TOOL_ROUNDS:
            logger.warning(
                "Agent %s hit tool-round cap (%d rounds)",
                agent_name,
                _MAX_TOOL_ROUNDS,
            )

        final_text = response.choices[0].message.content or ""
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
        """Stream events with an explicit system prompt."""
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        openai_tools = _to_openai_tools(tool_schemas)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        rounds = 0
        while rounds <= _MAX_TOOL_ROUNDS:
            rounds += 1

            accumulated_text = ""
            tool_calls: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None

            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=_MAX_TOKENS,
                stream=True,
                **({"tools": openai_tools} if openai_tools else {}),
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                delta = choice.delta
                if delta.content:
                    accumulated_text += delta.content
                    yield AgentEvent(
                        kind=EventKind.TEXT_DELTA,
                        agent_name=agent_name,
                        content=delta.content,
                    )

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls[idx]["name"] = tc_delta.function.name
                                yield AgentEvent(
                                    kind=EventKind.TOOL_CALL,
                                    agent_name=agent_name,
                                    content=tc_delta.function.name,
                                    tool_name=tc_delta.function.name,
                                )
                            if tc_delta.function.arguments:
                                tool_calls[idx]["arguments"] += (
                                    tc_delta.function.arguments
                                )

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            # If done (no tool calls), emit DONE and return.
            if finish_reason != "tool_calls":
                yield AgentEvent(
                    kind=EventKind.DONE,
                    agent_name=agent_name,
                    content="",
                )
                return

            # Append assistant message with tool calls.
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": accumulated_text or None}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls.values()
                ]
            messages.append(assistant_msg)

            # Execute tool calls and append results.
            for tc in tool_calls.values():
                args = json.loads(tc["arguments"])
                result = await self._tools.dispatch(tc["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )
                yield AgentEvent(
                    kind=EventKind.TOOL_RESULT,
                    agent_name=agent_name,
                    content=result[:500],
                    tool_name=tc["name"],
                )

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
        """
        tool_schemas = TOOL_SCHEMAS if tools is None else tools
        openai_tools = _to_openai_tools(tool_schemas)
        dispatch = tool_dispatch if tool_dispatch is not None else self._tools.dispatch

        rounds = 0
        while rounds <= _MAX_TOOL_ROUNDS:
            rounds += 1

            accumulated_text = ""
            tool_call_accum: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None

            # Prepend system prompt without mutating the caller's list.
            api_messages = [{"role": "system", "content": system_prompt}] + messages

            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=api_messages,
                max_tokens=_MAX_TOKENS,
                stream=True,
                **({"tools": openai_tools} if openai_tools else {}),
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                delta = choice.delta
                if delta.content:
                    accumulated_text += delta.content
                    yield AgentEvent(
                        kind=EventKind.TEXT_DELTA,
                        agent_name=agent_name,
                        content=delta.content,
                    )

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_accum:
                            tool_call_accum[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_call_accum[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_call_accum[idx]["name"] = tc_delta.function.name
                                yield AgentEvent(
                                    kind=EventKind.TOOL_CALL,
                                    agent_name=agent_name,
                                    content=tc_delta.function.name,
                                    tool_name=tc_delta.function.name,
                                )
                            if tc_delta.function.arguments:
                                tool_call_accum[idx]["arguments"] += (
                                    tc_delta.function.arguments
                                )

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            # Append assistant turn to the caller's message list.
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": accumulated_text or None}
            if tool_call_accum:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_call_accum.values()
                ]
            messages.append(assistant_msg)

            # If done (no tool calls), emit DONE and return.
            if finish_reason != "tool_calls":
                yield AgentEvent(
                    kind=EventKind.DONE,
                    agent_name=agent_name,
                    content="",
                )
                return

            # Execute tool calls and append results.
            for tc in tool_call_accum.values():
                args = json.loads(tc["arguments"])
                result = await dispatch(tc["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )
                yield AgentEvent(
                    kind=EventKind.TOOL_RESULT,
                    agent_name=agent_name,
                    content=result[:500],
                    tool_name=tc["name"],
                )

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
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> openai.types.chat.ChatCompletion:
        """Wrapper around ``chat.completions.create`` with sensible defaults."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return await self._client.chat.completions.create(**kwargs)


# ------------------------------------------------------------------
# Module-private helpers
# ------------------------------------------------------------------


def _to_openai_tools(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-format tool schemas to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s["input_schema"],
            },
        }
        for s in schemas
    ]


def _message_to_dict(msg: Any) -> dict[str, Any]:
    """Convert an OpenAI ChatCompletionMessage to a plain dict for the message list."""
    d: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


def _summarise_args(args: dict[str, Any]) -> str:
    """Produce a short summary of tool arguments for reasoning steps."""
    parts = [f"{k}={v!r}" for k, v in args.items()]
    summary = ", ".join(parts)
    if len(summary) > 120:
        return summary[:117] + "..."
    return summary


def _extract_signals(text: str) -> list[str]:
    """Extract signal-like statements from the final analysis text."""
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
