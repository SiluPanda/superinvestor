from __future__ import annotations

from pydantic import Field

from .base import SuperInvestorBase
from .enums import AnalystRole, EventKind


class AgentEvent(SuperInvestorBase):
    """A single event emitted during streaming agent execution."""

    kind: EventKind
    agent_name: str
    content: str
    tool_name: str | None = None


class TaskRequest(SuperInvestorBase):
    """Input to an agent run: what to analyze and which analysts to use."""

    prompt: str
    tickers: list[str] = Field(default_factory=list)
    analyst_roles: list[AnalystRole] = Field(
        default_factory=lambda: [
            AnalystRole.FUNDAMENTAL,
            AnalystRole.TECHNICAL,
            AnalystRole.SENTIMENT,
            AnalystRole.FILING,
            AnalystRole.SUPERINVESTOR,
        ]
    )


class TaskResult(SuperInvestorBase):
    """Output of an agent run: the analysis text, reasoning trace, and extracted signals."""

    summary: str
    agent_name: str
    reasoning_steps: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
