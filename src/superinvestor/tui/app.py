from __future__ import annotations

import asyncio
import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from superinvestor.agents.registry import DataStack, create_stack
from superinvestor.config import Settings
from superinvestor.mcp.client import McpManager
from superinvestor.store.db import Database
from superinvestor.tui.chat import ChatSession
from superinvestor.tui.commands import parse_command
from superinvestor.tui.widgets.chat_input import ChatInput
from superinvestor.tui.widgets.message_list import (
    AssistantMessage,
    LoopStatus,
    MessageList,
    ToolIndicator,
)
from superinvestor.tui.widgets.side_panel import SidePanel

logger = logging.getLogger(__name__)

_DATA_TOOL_KEYWORDS = {"quote", "price", "ohlcv", "market", "filing", "edgar", "sec", "fred", "economic", "news"}


def _tool_label(tool_name: str) -> str:
    """Map a tool name to a human-readable action label."""
    lower = tool_name.lower()
    if any(kw in lower for kw in _DATA_TOOL_KEYWORDS):
        return "Reading"
    return "Computing"


_WELCOME = (
    "Welcome to [bold]superinvestor[/bold]. "
    "Type a message to chat, or use /help to see commands."
)


class SuperInvestorApp(App[None]):
    """Chat-first terminal UI for superinvestor."""

    TITLE = "superinvestor"

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main-layout {
        height: 1fr;
    }

    #chat-area {
        width: 1fr;
    }

    MessageList {
        height: 1fr;
        padding: 1 1;
        scrollbar-size: 1 1;
    }

    UserMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
    }

    AssistantMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: #a8d8a8;
    }

    SystemMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text-muted;
        text-style: italic;
    }

    ToolIndicator {
        padding: 0 1 0 3;
        color: #5f8787;
    }

    LoopStatus {
        dock: bottom;
        height: auto;
        padding: 0 2;
        color: #5f8787;
        display: none;
    }

    ChatInput {
        dock: bottom;
        margin: 0 1;
    }

    SidePanel {
        width: 36;
        border-left: solid $surface-lighten-2;
        padding: 1 0;
        overflow-y: auto;
    }

    SidePanel DataTable {
        height: auto;
        max-height: 12;
    }

    Collapsible {
        padding: 0 1;
    }

    CollapsibleTitle {
        color: $accent;
        text-style: bold;
    }

    DataTable {
        scrollbar-size: 1 1;
    }

    DataTable > .datatable--header {
        color: $text-muted;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+p", "toggle_panel", "Panel", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings()
        self._database = Database(self._settings.db_path)
        self.stack: DataStack | None = None
        self.db_conn = None
        self.mcp_manager = McpManager()
        self.session: ChatSession | None = None
        self._busy = False
        self._loop_task: asyncio.Task[None] | None = None
        self._loop_prompt: str = ""
        self._loop_interval: float = 0.0

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="chat-area"):
                yield MessageList()
                yield LoopStatus(id="loop-status")
                yield ChatInput()
            yield SidePanel()

    async def on_mount(self) -> None:
        self.db_conn = await self._database.connect()
        self.stack = create_stack(self._settings)
        self.session = ChatSession(self.stack.provider, self.mcp_manager)
        self.session.bind_app(self)

        # Load side panel data.
        panel = self.query_one(SidePanel)
        await panel.refresh_data(self.db_conn)

        # Welcome message.
        msg_list = self.query_one(MessageList)
        msg_list.add_system_message(_WELCOME)

        # Focus the input.
        self.query_one(ChatInput).focus()

    async def on_unmount(self) -> None:
        self.stop_loop()
        if self.session:
            self.session = None
        await self.mcp_manager.close()
        if self.stack:
            await self.stack.close()
        await self._database.close()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_chat_input_chat_submitted(self, event: ChatInput.ChatSubmitted) -> None:
        """Handle user input from the chat bar."""
        text = event.text
        if not text or self._busy:
            return

        msg_list = self.query_one(MessageList)

        # Check for /clear special case.
        parsed = parse_command(text)
        if parsed is not None and parsed[0] == "clear":
            msg_list.clear_messages()
            if self.session:
                self.session.clear()
            return

        # Show user message in chat.
        msg_list.add_user_message(text)

        # Dispatch to session in a worker to keep UI responsive.
        self.run_worker(self._process_input(text), exclusive=True)

    async def _process_input(self, text: str) -> None:
        """Process user input through the chat session (runs in a worker)."""
        if self.session is None:
            return

        self._busy = True
        msg_list = self.query_one(MessageList)
        assistant_msg: AssistantMessage | None = None
        accumulated = ""
        current_tool: ToolIndicator | None = None

        msg_list.show_thinking("Thinking")

        try:
            async for event in self.session.send(text):
                if event.kind.value == "agent_switch":
                    # Flush current assistant message, start new section.
                    if accumulated:
                        assistant_msg = None
                        accumulated = ""
                    msg_list.hide_thinking()
                    msg_list.add_system_message(f"● {event.content}")
                    msg_list.show_thinking("Analyzing")
                    current_tool = None

                elif event.kind.value == "text_delta":
                    msg_list.hide_thinking()
                    if assistant_msg is None:
                        assistant_msg = msg_list.add_assistant_message()
                    accumulated += event.content
                    assistant_msg.update(accumulated)
                    msg_list.scroll_end(animate=False)

                elif event.kind.value == "tool_call":
                    tool_name = event.tool_name or event.content
                    msg_list.show_thinking(_tool_label(tool_name))
                    current_tool = msg_list.add_tool_indicator(tool_name)

                elif event.kind.value == "tool_result":
                    if current_tool is not None:
                        label = str(current_tool.render())
                        current_tool.update(label.replace("...", " done"))
                        current_tool = None
                    msg_list.show_thinking("Thinking")

                elif event.kind.value == "error":
                    msg_list.hide_thinking()
                    msg_list.add_system_message(f"[red]Error: {event.content}[/red]")

                elif event.kind.value == "done":
                    msg_list.hide_thinking()

        except Exception as exc:
            logger.error("Error processing input: %s", exc, exc_info=True)
            msg_list.add_system_message(f"[red]Error: {exc}[/red]")
        finally:
            msg_list.hide_thinking()
            self._busy = False

        # Refresh side panel after any command that might have changed data.
        if self.db_conn is not None:
            panel = self.query_one(SidePanel)
            await panel.refresh_data(self.db_conn)

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    @property
    def loop_active(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    @property
    def loop_interval(self) -> float:
        return self._loop_interval

    @property
    def loop_prompt(self) -> str:
        return self._loop_prompt

    async def start_loop(self, interval: float, prompt: str) -> None:
        """Start a recurring loop that executes *prompt* every *interval* seconds."""
        self.stop_loop()
        self._loop_prompt = prompt
        self._loop_interval = interval
        self._loop_task = asyncio.create_task(self._loop_runner())
        self._update_loop_indicator()

    def stop_loop(self) -> str:
        """Cancel the running loop. Returns a status message."""
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None
            self._loop_prompt = ""
            self._loop_interval = 0.0
            self._update_loop_indicator()
            return "Loop stopped."
        return "No loop is running."

    async def _loop_runner(self) -> None:
        """Core loop coroutine: sleep → wait for idle → execute prompt."""
        msg_list = self.query_one(MessageList)
        iteration = 0
        try:
            while True:
                await asyncio.sleep(self._loop_interval)
                iteration += 1

                # Wait for any active user input to finish.
                while self._busy:
                    await asyncio.sleep(1.0)

                msg_list.add_system_message(
                    f"[dim]Loop iteration {iteration} — {self._loop_prompt}[/dim]"
                )
                await self._process_input(self._loop_prompt)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Loop runner failed: %s", exc, exc_info=True)
            msg_list.add_system_message(f"[red]Loop stopped due to error: {exc}[/red]")
        finally:
            self._loop_task = None
            self._loop_prompt = ""
            self._loop_interval = 0.0
            self._update_loop_indicator()

    def _update_loop_indicator(self) -> None:
        """Show or hide the loop status bar."""
        from superinvestor.tui.commands import format_interval

        try:
            indicator = self.query_one("#loop-status", LoopStatus)
        except Exception:
            return
        if self.loop_active:
            indicator.update(
                f"  ↻ Loop active: every {format_interval(self._loop_interval)}"
                f" — {self._loop_prompt}"
                f"  [dim](/loop stop to cancel)[/dim]"
            )
            indicator.display = True
        else:
            indicator.display = False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_clear_chat(self) -> None:
        """Clear the chat message list."""
        self.query_one(MessageList).clear_messages()
        if self.session:
            self.session.clear()

    def action_toggle_panel(self) -> None:
        """Toggle the side panel visibility."""
        panel = self.query_one(SidePanel)
        panel.display = not panel.display
