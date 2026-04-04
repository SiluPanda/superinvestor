from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from superinvestor.agents.prompts import ANALYST_PROMPTS
from superinvestor.agents.providers.anthropic import AnthropicProvider
from superinvestor.models.agent import AgentEvent, TaskResult
from superinvestor.models.enums import AnalystRole, EventKind

logger = logging.getLogger(__name__)

# The default set of analysts to run (excludes SYNTHESIZER, which is phase 2).
_DEFAULT_ROLES: list[AnalystRole] = [
    AnalystRole.FUNDAMENTAL,
    AnalystRole.TECHNICAL,
    AnalystRole.SENTIMENT,
]


async def run_analysis(
    provider: AnthropicProvider,
    tickers: list[str],
    analyst_roles: list[AnalystRole] | None = None,
) -> TaskResult:
    """Run multi-agent stock analysis: parallel analysts -> synthesizer.

    Phase 1 runs each analyst role concurrently with tool access.
    Phase 2 passes the collected reports to the synthesizer (no tools)
    to produce a final recommendation.

    Parameters
    ----------
    provider:
        The Anthropic provider instance with tools bound.
    tickers:
        Stock tickers to analyze.
    analyst_roles:
        Which analyst roles to run.  Defaults to fundamental, technical,
        and sentiment.  SYNTHESIZER should not be included here — it is
        always run as the final phase.
    """
    roles = analyst_roles or _DEFAULT_ROLES
    # Filter out synthesizer from the analyst phase — it runs separately.
    roles = [r for r in roles if r != AnalystRole.SYNTHESIZER]
    ticker_str = ", ".join(t.upper() for t in tickers)

    # ------------------------------------------------------------------
    # Phase 1: Run analysts in parallel
    # ------------------------------------------------------------------

    async def run_analyst(role: AnalystRole) -> TaskResult:
        system_prompt = ANALYST_PROMPTS.get(role)
        if system_prompt is None:
            logger.warning("No prompt defined for role %s, using generic", role)
            system_prompt = f"You are a {role.value} analyst. Analyze the given stocks."

        user_prompt = f"Analyze the following stocks: {ticker_str}"
        return await provider.run_with_system(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            agent_name=role.value,
        )

    analyst_results = await asyncio.gather(
        *(run_analyst(role) for role in roles),
        return_exceptions=True,
    )

    # Separate successes from failures.
    successes: list[TaskResult] = []
    for role, result in zip(roles, analyst_results):
        if isinstance(result, BaseException):
            logger.error("Analyst %s failed: %s", role.value, result)
            successes.append(
                TaskResult(
                    summary=f"[Analysis failed: {result}]",
                    agent_name=role.value,
                    reasoning_steps=[f"Error: {result}"],
                    signals=[],
                )
            )
        else:
            successes.append(result)

    # ------------------------------------------------------------------
    # Phase 2: Synthesize
    # ------------------------------------------------------------------

    reports = "\n\n---\n\n".join(
        f"## {result.agent_name.replace('_', ' ').title()} Analysis\n\n{result.summary}"
        for result in successes
    )

    synth_system = ANALYST_PROMPTS.get(AnalystRole.SYNTHESIZER, "")
    if not synth_system:
        synth_system = (
            "Synthesize the following analyst reports into a final investment recommendation."
        )

    synth_prompt = (
        f"Here are the analyst reports for {ticker_str}:\n\n"
        f"{reports}\n\n"
        f"Synthesize these into a final investment recommendation."
    )

    synthesis = await provider.run_with_system(
        system_prompt=synth_system,
        user_prompt=synth_prompt,
        agent_name="synthesizer",
        tools=[],  # Synthesizer does not get tools.
    )

    # ------------------------------------------------------------------
    # Merge results
    # ------------------------------------------------------------------

    all_steps: list[str] = []
    for r in successes:
        all_steps.extend(f"[{r.agent_name}] {s}" for s in r.reasoning_steps)
    all_steps.extend(f"[synthesizer] {s}" for s in synthesis.reasoning_steps)

    return TaskResult(
        summary=synthesis.summary,
        agent_name="pipeline",
        reasoning_steps=all_steps,
        signals=synthesis.signals,
    )


async def stream_analysis(
    provider: AnthropicProvider,
    tickers: list[str],
    analyst_roles: list[AnalystRole] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream a multi-agent analysis, yielding events from each phase.

    Analysts run sequentially in streaming mode so events arrive in order.
    The synthesizer streams last.
    """
    roles = analyst_roles or _DEFAULT_ROLES
    roles = [r for r in roles if r != AnalystRole.SYNTHESIZER]
    ticker_str = ", ".join(t.upper() for t in tickers)

    analyst_summaries: list[tuple[str, str]] = []

    # Phase 1: Stream each analyst sequentially.
    for role in roles:
        system_prompt = ANALYST_PROMPTS.get(role)
        if system_prompt is None:
            system_prompt = f"You are a {role.value} analyst. Analyze the given stocks."

        user_prompt = f"Analyze the following stocks: {ticker_str}"

        yield AgentEvent(
            kind=EventKind.AGENT_SWITCH,
            agent_name=role.value,
            content=f"Starting {role.value} analysis",
        )

        accumulated = ""
        try:
            async for event in provider.stream_with_system(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=role.value,
            ):
                if event.kind == EventKind.TEXT_DELTA:
                    accumulated += event.content
                yield event
        except Exception as exc:
            logger.error("Analyst %s failed during streaming: %s", role.value, exc)
            accumulated = f"[Analysis failed: {exc}]"
            yield AgentEvent(
                kind=EventKind.ERROR,
                agent_name=role.value,
                content=str(exc),
            )

        analyst_summaries.append((role.value, accumulated))

    # Phase 2: Synthesize.
    reports = "\n\n---\n\n".join(
        f"## {name.replace('_', ' ').title()} Analysis\n\n{summary}"
        for name, summary in analyst_summaries
    )

    synth_system = ANALYST_PROMPTS.get(AnalystRole.SYNTHESIZER, "")
    if not synth_system:
        synth_system = (
            "Synthesize the following analyst reports into a final investment recommendation."
        )

    synth_prompt = (
        f"Here are the analyst reports for {ticker_str}:\n\n"
        f"{reports}\n\n"
        f"Synthesize these into a final investment recommendation."
    )

    yield AgentEvent(
        kind=EventKind.AGENT_SWITCH,
        agent_name="synthesizer",
        content="Starting synthesis",
    )

    async for event in provider.stream_with_system(
        system_prompt=synth_system,
        user_prompt=synth_prompt,
        agent_name="synthesizer",
        tools=[],
    ):
        yield event
