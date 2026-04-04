from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superinvestor.tui.app import SuperInvestorApp
from superinvestor.tui.widgets.chat_input import ChatInput
from superinvestor.tui.widgets.message_list import MessageList, SystemMessage
from superinvestor.tui.widgets.side_panel import SidePanel


def _make_app() -> SuperInvestorApp:
    """Create an app with mocked backend so no real DB/API calls happen."""
    with patch("superinvestor.tui.app.Settings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings.db_path = Path(":memory:")
        mock_settings_cls.return_value = mock_settings
        app = SuperInvestorApp()
    return app


@pytest.fixture
def app() -> SuperInvestorApp:
    return _make_app()


class TestAppLayout:
    @pytest.mark.asyncio
    async def test_app_has_message_list(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    assert app.query_one(MessageList) is not None

    @pytest.mark.asyncio
    async def test_app_has_chat_input(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    assert app.query_one(ChatInput) is not None

    @pytest.mark.asyncio
    async def test_app_has_side_panel(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    assert app.query_one(SidePanel) is not None

    @pytest.mark.asyncio
    async def test_welcome_message_shown(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    msg_list = app.query_one(MessageList)
                    system_msgs = msg_list.query(SystemMessage)
                    assert len(system_msgs) >= 1


class TestAppActions:
    @pytest.mark.asyncio
    async def test_clear_chat(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    msg_list = app.query_one(MessageList)
                    # Verify there's at least the welcome message.
                    assert len(msg_list.query(SystemMessage)) >= 1
                    # Clear.
                    app.action_clear_chat()
                    await _pilot.pause()
                    assert len(msg_list.children) == 0

    @pytest.mark.asyncio
    async def test_toggle_panel(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    panel = app.query_one(SidePanel)
                    assert panel.display is True
                    app.action_toggle_panel()
                    assert panel.display is False
                    app.action_toggle_panel()
                    assert panel.display is True

    @pytest.mark.asyncio
    async def test_side_panel_has_three_collapsibles(self, app: SuperInvestorApp) -> None:
        with (
            patch("superinvestor.tui.app.Database") as mock_db_cls,
            patch("superinvestor.tui.app.create_stack") as mock_stack,
        ):
            mock_db = MagicMock()
            mock_db.connect = AsyncMock(return_value=MagicMock())
            mock_db.close = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_stack_inst = MagicMock()
            mock_stack_inst.close = AsyncMock()
            mock_stack.return_value = mock_stack_inst

            with patch.object(SidePanel, "refresh_data", new_callable=AsyncMock):
                async with app.run_test() as _pilot:
                    from textual.widgets import Collapsible

                    panel = app.query_one(SidePanel)
                    collapsibles = panel.query(Collapsible)
                    assert len(collapsibles) == 3
