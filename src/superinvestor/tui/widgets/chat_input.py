from __future__ import annotations

from textual.message import Message
from textual.widgets import Input


class ChatInput(Input):
    """Chat input bar at the bottom of the screen."""

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 0 1;
        border-top: solid $surface-lighten-2;
    }
    """

    class ChatSubmitted(Message):
        """Posted when the user submits a chat message."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self) -> None:
        super().__init__(placeholder="> Type a message or /command...")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key -- post our custom ChatSubmitted message and clear."""
        text = event.value.strip()
        if not text:
            return
        event.stop()
        self.clear()
        self.post_message(self.ChatSubmitted(text))
