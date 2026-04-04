from __future__ import annotations

from typing import AsyncIterator, Protocol

from superinvestor.models.agent import AgentEvent, TaskRequest, TaskResult


class AgentProvider(Protocol):
    """Thin protocol for AI agent providers.

    Each provider implements this using its native SDK patterns.
    The protocol only standardizes input/output — agent construction,
    tool binding, and multi-agent orchestration are provider-internal.
    """

    async def run(self, task: TaskRequest) -> TaskResult: ...

    def stream(self, task: TaskRequest) -> AsyncIterator[AgentEvent]: ...
