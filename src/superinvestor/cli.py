from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Coroutine

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer(name="superinvestor", help="AI-powered quantitative trading agent harness")
console = Console()


def main() -> None:
    """Entrypoint: launch TUI if no subcommand, otherwise delegate to Typer."""
    if len(sys.argv) == 1:
        from superinvestor.tui.app import SuperInvestorApp

        SuperInvestorApp().run()
    else:
        app()


def _run_async(coro: Coroutine[object, object, None]) -> None:
    """Run an async coroutine from synchronous CLI context."""
    asyncio.run(coro)


@app.command()
def analyze(
    ticker: str = typer.Argument(help="Stock ticker to analyze (e.g., AAPL)"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream output in real-time"),
) -> None:
    """Run AI analysis on a stock."""
    _run_async(_analyze(ticker, stream))


async def _analyze(ticker: str, stream: bool) -> None:
    from superinvestor.agents.registry import create_stack
    from superinvestor.engine.pipeline import run_analysis, stream_analysis
    from superinvestor.models.enums import EventKind

    stack = create_stack()

    try:
        if stream:
            console.print(f"\n[bold]Analyzing {ticker}...[/bold]\n")
            async for event in stream_analysis(
                stack.provider,
                [ticker.upper()],
            ):
                if event.kind == EventKind.AGENT_SWITCH:
                    console.print(f"\n[bold cyan]--- {event.content} ---[/bold cyan]")
                elif event.kind == EventKind.TEXT_DELTA:
                    console.print(event.content, end="")
                elif event.kind == EventKind.TOOL_CALL:
                    console.print(
                        f"\n[dim]  tool: {event.tool_name}({event.content})[/dim]", end=""
                    )
                elif event.kind == EventKind.TOOL_RESULT:
                    console.print(" [dim green]done[/dim green]")
                elif event.kind == EventKind.ERROR:
                    console.print(f"\n[red]Error: {event.content}[/red]")
            console.print()
        else:
            with console.status(f"[bold]Analyzing {ticker}...[/bold]"):
                result = await run_analysis(stack.provider, [ticker.upper()])

            console.print(
                Panel(
                    Markdown(result.summary),
                    title=f"Analysis: {ticker.upper()}",
                    border_style="green",
                )
            )

            if result.reasoning_steps:
                console.print(f"\n[dim]Reasoning steps: {len(result.reasoning_steps)}[/dim]")
                for step in result.reasoning_steps[:10]:
                    console.print(f"  [dim]{step}[/dim]")
                if len(result.reasoning_steps) > 10:
                    console.print(f"  [dim]... and {len(result.reasoning_steps) - 10} more[/dim]")
    finally:
        await stack.close()


@app.command()
def configure() -> None:
    """Open the configuration file in your editor."""
    from superinvestor.config import CONFIG_PATH, ensure_config

    created = ensure_config()
    if created:
        console.print(f"Created config at {CONFIG_PATH}")

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(CONFIG_PATH)])


@app.command()
def tui() -> None:
    """Launch the terminal UI."""
    from superinvestor.tui.app import SuperInvestorApp

    SuperInvestorApp().run()


@app.command()
def watch(
    tickers: list[str] = typer.Argument(help="Tickers to add to watchlist"),
) -> None:
    """Add tickers to the watchlist."""
    for t in tickers:
        console.print(f"Added [bold]{t.upper()}[/bold] to watchlist")


@app.command()
def portfolio() -> None:
    """Show paper trading portfolio."""
    console.print("Paper portfolio not yet implemented (Phase 6)")


@app.command()
def monitor() -> None:
    """Start 24/7 monitoring daemon."""
    console.print("Monitor not yet implemented (Phase 6)")


if __name__ == "__main__":
    app()
