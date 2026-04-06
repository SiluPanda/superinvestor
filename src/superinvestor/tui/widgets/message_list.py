from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static


class UserMessage(Static):
    """A user message in the chat."""

    DEFAULT_CSS = """
    UserMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
    }
    """


class AssistantMessage(Static):
    """An assistant message that supports streaming updates."""

    DEFAULT_CSS = """
    AssistantMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: #a8d8a8;
    }
    """


class SystemMessage(Static):
    """A system/status message."""

    DEFAULT_CSS = """
    SystemMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text-muted;
        text-style: italic;
    }
    """


class ToolIndicator(Static):
    """Shows a tool call status."""

    DEFAULT_CSS = """
    ToolIndicator {
        padding: 0 1 0 3;
        color: #5f8787;
    }
    """


class ThinkingIndicator(Static):
    """Animated blinking indicator shown while the model is processing."""

    DEFAULT_CSS = """
    ThinkingIndicator {
        padding: 0 2;
        color: #5f8787;
        display: none;
    }
    """

    def __init__(self, id: str | None = None) -> None:  # noqa: A002
        super().__init__("", id=id)
        self._phase = False
        self._label = "Thinking"

    def on_mount(self) -> None:
        self.set_interval(0.5, self._tick)

    def _tick(self) -> None:
        if self.display:
            self._phase = not self._phase
            self._render_frame()

    def _render_frame(self) -> None:
        dot = "■" if self._phase else "□"
        self.update(f"  {dot} [dim]{self._label}[/dim]")

    def show(self, label: str = "Thinking") -> None:
        """Show the indicator with the given label."""
        self._label = label
        self._phase = True
        self._render_frame()
        self.display = True

    def hide(self) -> None:
        """Hide the indicator."""
        self.display = False


class LoopStatus(Static):
    """Status bar shown when a recurring loop is active."""

    DEFAULT_CSS = """
    LoopStatus {
        padding: 0 2;
        color: #5f8787;
        display: none;
    }
    """


class MessageList(VerticalScroll):
    """Scrollable list of chat messages."""

    DEFAULT_CSS = """
    MessageList {
        height: 1fr;
        padding: 1 0;
    }
    """

    def add_user_message(self, text: str) -> UserMessage:
        """Add a user message and scroll to bottom."""
        msg = UserMessage(f"[bold]> {text}[/bold]")
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_assistant_message(self) -> AssistantMessage:
        """Add an empty assistant message widget for streaming. Returns handle."""
        msg = AssistantMessage("")
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_system_message(self, text: str) -> SystemMessage:
        """Add a system/status message."""
        msg = SystemMessage(text)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def add_tool_indicator(self, tool_name: str) -> ToolIndicator:
        """Add a tool call indicator."""
        indicator = ToolIndicator(f"  ├ {tool_name}...")
        self.mount(indicator)
        self.scroll_end(animate=False)
        return indicator

    def clear_messages(self) -> None:
        """Remove all messages."""
        self.remove_children()
