from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from superinvestor.mcp.client import McpManager
    from superinvestor.tui.app import SuperInvestorApp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(app: SuperInvestorApp) -> aiosqlite.Connection:
    """Return the app's database connection, raising if not yet initialised."""
    if app.db_conn is None:
        raise RuntimeError("Database connection is not available yet.")
    return app.db_conn


def _get_mcp(app: SuperInvestorApp) -> McpManager:
    """Return the app's MCP manager, raising if not present."""
    manager: McpManager | None = getattr(app, "mcp_manager", None)
    if manager is None:
        raise RuntimeError("MCP manager is not available.")
    return manager


# ---------------------------------------------------------------------------
# Result / registry types
# ---------------------------------------------------------------------------


@dataclass
class CommandResult:
    """Result of a slash command execution."""

    text: str  # Message to display in chat (system message)
    stream: bool = False  # If True, text is ignored and the command handles its own streaming


@dataclass
class CommandInfo:
    name: str
    description: str
    usage: str  # e.g. "/analyze <ticker>"
    handler: Callable[..., Awaitable[CommandResult]]


# ---------------------------------------------------------------------------
# Parsing / dispatch
# ---------------------------------------------------------------------------


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse a slash command from raw input text.

    Returns ``(command_name, args_string)`` or ``None`` if *text* is not
    a command.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(maxsplit=1)
    command_name = parts[0][1:]  # drop the leading "/"
    args_string = parts[1] if len(parts) > 1 else ""
    return command_name, args_string


async def dispatch(app: SuperInvestorApp, command_name: str, args_string: str) -> CommandResult:
    """Look up *command_name* in the registry and call its handler."""
    info = COMMANDS.get(command_name)
    if info is None:
        return CommandResult(
            text=f"Unknown command: /{command_name}. Type /help for available commands."
        )
    try:
        return await info.handler(app, args_string)
    except Exception:
        logger.exception("Command /%s failed", command_name)
        return CommandResult(text=f"Error running /{command_name}. Check the logs for details.")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_help(app: SuperInvestorApp, args: str) -> CommandResult:
    """List all available slash commands."""
    lines: list[str] = ["Available commands:\n"]
    for info in COMMANDS.values():
        lines.append(f"  {info.usage:<30s} {info.description}")
    return CommandResult(text="\n".join(lines))


async def cmd_clear(app: SuperInvestorApp, args: str) -> CommandResult:
    """Signal the app to clear the chat history."""
    return CommandResult(text="", stream=False)


async def cmd_analyze(app: SuperInvestorApp, args: str) -> CommandResult:
    """Validate ticker and signal the app to start a streaming analysis."""
    ticker = args.strip().upper()
    if not ticker:
        return CommandResult(text="Usage: /analyze <ticker>")
    return CommandResult(text="", stream=True)


async def cmd_save(app: SuperInvestorApp, args: str) -> CommandResult:
    """Signal the app to extract and persist an investment thesis."""
    return CommandResult(text="Saving thesis...", stream=True)


async def cmd_watch(app: SuperInvestorApp, args: str) -> CommandResult:
    """Add a ticker to the watchlist."""
    from superinvestor.models.watchlist import WatchlistItem
    from superinvestor.store.watchlist_store import WatchlistStore

    ticker = args.strip().split()[0].upper() if args.strip() else ""
    if not ticker:
        return CommandResult(text="Usage: /watch <ticker> [notes]")

    db = _get_db(app)
    store = WatchlistStore(db)
    if await store.exists(ticker):
        return CommandResult(text=f"{ticker} is already on the watchlist.")

    notes = " ".join(args.strip().split()[1:])
    item = WatchlistItem(ticker=ticker, notes=notes)
    await store.insert(item)
    return CommandResult(text=f"Added {ticker} to watchlist.")


async def cmd_unwatch(app: SuperInvestorApp, args: str) -> CommandResult:
    """Remove a ticker from the watchlist."""
    from superinvestor.store.watchlist_store import WatchlistStore

    ticker = args.strip().upper()
    if not ticker:
        return CommandResult(text="Usage: /unwatch <ticker>")

    db = _get_db(app)
    store = WatchlistStore(db)
    item = await store.get_by_ticker(ticker)
    if item is None:
        return CommandResult(text=f"{ticker} is not on the watchlist.")

    await store.delete_by_id(item.id)
    return CommandResult(text=f"Removed {ticker} from watchlist.")


async def cmd_thesis(app: SuperInvestorApp, args: str) -> CommandResult:
    """List saved investment theses, optionally filtered by ticker."""
    from superinvestor.store.thesis_store import ThesisStore

    db = _get_db(app)
    store = ThesisStore(db)
    ticker = args.strip().upper()

    if ticker:
        theses = await store.get_active(ticker)
    else:
        theses = await store.get_all_active()

    if not theses:
        label = f" for {ticker}" if ticker else ""
        return CommandResult(text=f"No active theses{label}.")

    lines: list[str] = []
    for t in theses:
        conf = f"{t.confidence_score:.0%}"
        target = f"  target=${t.target_price}" if t.target_price else ""
        lines.append(f"  [{t.status.value}] {t.ticker}: {t.title}  (confidence {conf}{target})")
    header = f"Active theses ({len(theses)}):\n"
    return CommandResult(text=header + "\n".join(lines))


async def cmd_history(app: SuperInvestorApp, args: str) -> CommandResult:
    """Show past analysis results, optionally filtered by ticker."""
    from superinvestor.store.analysis_store import AnalysisStore

    db = _get_db(app)
    store = AnalysisStore(db)
    ticker = args.strip().upper()

    if ticker:
        results = await store.get_recent(ticker, limit=10)
    else:
        results = await store.query(order_by="created_at DESC", limit=10)

    if not results:
        label = f" for {ticker}" if ticker else ""
        return CommandResult(text=f"No analysis history{label}.")

    lines: list[str] = []
    for r in results:
        ts = r.created_at.strftime("%Y-%m-%d %H:%M")
        conf = f"{r.confidence:.0%}"
        lines.append(f"  {ts}  {r.ticker:<6s} {r.title}  (confidence {conf})")
    header = f"Recent analyses ({len(results)}):\n"
    return CommandResult(text=header + "\n".join(lines))


_INTERVAL_RE = re.compile(r"^(\d+)\s*([smh])?$")
_DEFAULT_INTERVAL = 600.0  # 10 minutes
_MIN_INTERVAL = 10.0  # seconds


def _parse_interval(token: str) -> float | None:
    """Parse an interval string like ``5m``, ``30s``, ``1h`` to seconds."""
    m = _INTERVAL_RE.match(token.strip().lower())
    if m is None:
        return None
    value = int(m.group(1))
    unit = m.group(2) or "m"
    return float(value * {"s": 1, "m": 60, "h": 3600}[unit])


def format_interval(seconds: float) -> str:
    if seconds >= 3600:
        return f"{seconds / 3600:.0f}h"
    if seconds >= 60:
        return f"{seconds / 60:.0f}m"
    return f"{seconds:.0f}s"


async def cmd_loop(app: SuperInvestorApp, args: str) -> CommandResult:
    """Start, stop, or check a recurring loop."""
    tokens = args.strip()

    if not tokens:
        return CommandResult(
            text="Usage: /loop [interval] <prompt or /command>\n"
            "       /loop stop\n"
            "       /loop status\n"
            "Default interval is 10m."
        )

    first_word = tokens.split()[0].lower()

    if first_word in ("stop", "cancel"):
        msg = app.stop_loop()
        return CommandResult(text=msg)

    if first_word == "status":
        if app.loop_active:
            return CommandResult(
                text=f"Loop active: every {format_interval(app.loop_interval)}"
                f" — {app.loop_prompt}"
            )
        return CommandResult(text="No loop is running.")

    # Parse optional interval prefix.
    parts = tokens.split(maxsplit=1)
    interval = _parse_interval(parts[0])

    if interval is not None:
        prompt = parts[1] if len(parts) > 1 else ""
    else:
        interval = _DEFAULT_INTERVAL
        prompt = tokens

    if not prompt.strip():
        return CommandResult(text="Usage: /loop [interval] <prompt or /command>")

    # Guard against recursive loops.
    inner_parsed = parse_command(prompt)
    if inner_parsed and inner_parsed[0] == "loop":
        return CommandResult(text="Cannot nest /loop inside /loop.")

    if interval < _MIN_INTERVAL:
        return CommandResult(text=f"Minimum loop interval is {_MIN_INTERVAL:.0f} seconds.")

    await app.start_loop(interval, prompt)
    return CommandResult(
        text=f"Loop started: every {format_interval(interval)} — {prompt}"
    )


async def cmd_mcp(app: SuperInvestorApp, args: str) -> CommandResult:
    """Manage MCP server connections (add/list/remove)."""
    parts = args.strip().split()
    if not parts:
        return CommandResult(text="Usage: /mcp <add|list|remove> ...")

    sub = parts[0].lower()

    manager = _get_mcp(app)

    if sub == "list":
        servers = manager.list_servers()
        if not servers:
            return CommandResult(text="No MCP servers connected.")
        lines: list[str] = []
        for name, tools in servers:
            lines.append(f"  {name}: {', '.join(tools) if tools else '(no tools)'}")
        return CommandResult(text=f"Connected MCP servers ({len(servers)}):\n" + "\n".join(lines))

    if sub == "add":
        if len(parts) < 3:
            return CommandResult(text="Usage: /mcp add <name> <command> [args...]")
        return CommandResult(text="Connecting...", stream=True)

    if sub == "remove":
        if len(parts) < 2:
            return CommandResult(text="Usage: /mcp remove <name>")
        name = parts[1]
        removed = await manager.remove_server(name)
        if removed:
            return CommandResult(text=f"Removed MCP server '{name}'.")
        return CommandResult(text=f"No MCP server named '{name}'.")

    return CommandResult(text=f"Unknown subcommand: {sub}. Use add, list, or remove.")


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

COMMANDS: dict[str, CommandInfo] = {
    "help": CommandInfo(
        name="help",
        description="Show available commands",
        usage="/help",
        handler=cmd_help,
    ),
    "clear": CommandInfo(
        name="clear",
        description="Clear chat",
        usage="/clear",
        handler=cmd_clear,
    ),
    "analyze": CommandInfo(
        name="analyze",
        description="Run multi-agent stock analysis",
        usage="/analyze <ticker>",
        handler=cmd_analyze,
    ),
    "save": CommandInfo(
        name="save",
        description="Save last analysis as investment thesis",
        usage="/save [ticker]",
        handler=cmd_save,
    ),
    "watch": CommandInfo(
        name="watch",
        description="Add ticker to watchlist",
        usage="/watch <ticker> [notes]",
        handler=cmd_watch,
    ),
    "unwatch": CommandInfo(
        name="unwatch",
        description="Remove ticker from watchlist",
        usage="/unwatch <ticker>",
        handler=cmd_unwatch,
    ),
    "thesis": CommandInfo(
        name="thesis",
        description="List saved investment theses",
        usage="/thesis [ticker]",
        handler=cmd_thesis,
    ),
    "history": CommandInfo(
        name="history",
        description="Show past analyses",
        usage="/history [ticker]",
        handler=cmd_history,
    ),
    "mcp": CommandInfo(
        name="mcp",
        description="Manage MCP server connections",
        usage="/mcp <add|list|remove> ...",
        handler=cmd_mcp,
    ),
    "loop": CommandInfo(
        name="loop",
        description="Run a prompt/command on a recurring interval",
        usage="/loop [interval] <prompt>",
        handler=cmd_loop,
    ),
}
