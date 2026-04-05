from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option
from textual.widget import Widget

from superinvestor.tui.commands import COMMANDS


class ChatInput(Widget):
    """Chat input bar with slash-command autocomplete dropdown."""

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 0 1;
        height: auto;
    }

    ChatInput > Input {
        border-top: solid $surface-lighten-2;
    }

    ChatInput > OptionList {
        border: solid $surface-lighten-2;
        max-height: 10;
        background: $surface;
    }
    """

    class ChatSubmitted(Message):
        """Posted when the user submits a chat message."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        yield OptionList(id="cmd-suggestions")
        yield Input(placeholder="> Type a message or /command...", id="chat-input-field")

    def on_mount(self) -> None:
        self.query_one("#cmd-suggestions", OptionList).display = False

    def focus(self, scroll_visible: bool = True) -> Widget:
        self.query_one("#chat-input-field", Input).focus()
        return self

    # ------------------------------------------------------------------
    # Input change — update dropdown
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        suggestions = self.query_one("#cmd-suggestions", OptionList)
        text = event.value

        # Only show dropdown for "/prefix" with no spaces (not yet in args phase)
        if text.startswith("/") and " " not in text:
            prefix = text[1:]  # everything after the slash
            matches = [
                info for name, info in COMMANDS.items()
                if name.startswith(prefix)
            ]
            suggestions.clear_options()
            for info in sorted(matches, key=lambda i: i.name):
                label = f"/{info.name}  —  {info.description}"
                suggestions.add_option(Option(label, id=info.name))
            suggestions.display = bool(matches)
        else:
            suggestions.display = False

    # ------------------------------------------------------------------
    # Keyboard — navigate / select / dismiss dropdown
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:  # noqa: ANN001
        suggestions = self.query_one("#cmd-suggestions", OptionList)
        if not suggestions.display:
            return

        if event.key == "escape":
            suggestions.display = False
            event.stop()

        elif event.key == "down":
            suggestions.action_cursor_down()
            event.stop()

        elif event.key == "up":
            suggestions.action_cursor_up()
            event.stop()

        elif event.key == "tab":
            self._select_highlighted(suggestions)
            event.stop()

    # ------------------------------------------------------------------
    # Submit — select from list or post ChatSubmitted
    # ------------------------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        suggestions = self.query_one("#cmd-suggestions", OptionList)

        # If dropdown is open and an item is highlighted, select it.
        if suggestions.display and suggestions.highlighted is not None:
            self._select_highlighted(suggestions)
            event.stop()
            return

        # Normal submit.
        text = event.value.strip()
        if not text:
            event.stop()
            return
        suggestions.display = False
        event.stop()
        inner = self.query_one("#chat-input-field", Input)
        inner.clear()
        self.post_message(self.ChatSubmitted(text))

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _select_highlighted(self, suggestions: OptionList) -> None:
        """Insert the highlighted command into the input and close the dropdown."""
        idx = suggestions.highlighted
        if idx is None:
            return
        option = suggestions.get_option_at_index(idx)
        command_name = option.id  # we stored the bare name as the option id
        inner = self.query_one("#chat-input-field", Input)
        inner.value = f"/{command_name} "
        inner.cursor_position = len(inner.value)
        suggestions.display = False
        inner.focus()
