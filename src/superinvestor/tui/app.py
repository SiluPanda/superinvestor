from __future__ import annotations

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
    MessageList,
    ToolIndicator,
)
from superinvestor.tui.widgets.side_panel import SidePanel

logger = logging.getLogger(__name__)

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

    ChatInput {
        dock: bottom;
        margin: 0 1;
        border-top: solid $surface-lighten-2;
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="chat-area"):
                yield MessageList()
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

        try:
            async for event in self.session.send(text):
                if event.kind.value == "agent_switch":
                    # Flush current assistant message, start new section.
                    if accumulated:
                        assistant_msg = None
                        accumulated = ""
                    msg_list.add_system_message(f"● {event.content}")
                    current_tool = None

                elif event.kind.value == "text_delta":
                    if assistant_msg is None:
                        assistant_msg = msg_list.add_assistant_message()
                    accumulated += event.content
                    assistant_msg.update(accumulated)
                    msg_list.scroll_end(animate=False)

                elif event.kind.value == "tool_call":
                    current_tool = msg_list.add_tool_indicator(event.tool_name or event.content)

                elif event.kind.value == "tool_result":
                    if current_tool is not None:
                        label = str(current_tool.render())
                        current_tool.update(label.replace("...", " done"))
                        current_tool = None

                elif event.kind.value == "error":
                    msg_list.add_system_message(f"[red]Error: {event.content}[/red]")

                elif event.kind.value == "done":
                    pass  # Natural end of stream.

        except Exception as exc:
            logger.error("Error processing input: %s", exc, exc_info=True)
            msg_list.add_system_message(f"[red]Error: {exc}[/red]")
        finally:
            self._busy = False

        # Refresh side panel after any command that might have changed data.
        if self.db_conn is not None:
            panel = self.query_one(SidePanel)
            await panel.refresh_data(self.db_conn)

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
