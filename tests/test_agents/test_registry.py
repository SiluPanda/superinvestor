from __future__ import annotations

import pytest

from superinvestor.agents.registry import create_stack
from superinvestor.config import Settings
from superinvestor.models.enums import ProviderName


class TestProviderValidation:
    def test_unsupported_provider_raises(self) -> None:
        settings = Settings(
            provider=ProviderName.OPENAI,
            polygon_api_key="fake",
            anthropic_api_key="fake",
            fred_api_key="fake",
        )
        with pytest.raises(ValueError, match="Unsupported provider"):
            create_stack(settings)

    def test_claude_provider_accepted(self) -> None:
        settings = Settings(
            provider=ProviderName.CLAUDE,
            polygon_api_key="fake",
            anthropic_api_key="fake",
            fred_api_key="fake",
        )
        stack = create_stack(settings)
        assert stack.provider is not None
