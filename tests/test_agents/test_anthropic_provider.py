from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superinvestor.agents.providers.anthropic import AnthropicProvider
from superinvestor.agents.tools import DomainTools
from superinvestor.models.agent import TaskRequest
from superinvestor.models.enums import AnalystRole


@pytest.fixture
def mock_tools() -> DomainTools:
    tools = MagicMock(spec=DomainTools)
    tools.dispatch = AsyncMock(return_value='{"price": "175.50", "ticker": "AAPL"}')
    return tools


@pytest.fixture
def provider(mock_tools: DomainTools) -> AnthropicProvider:
    return AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514", tools=mock_tools)


@pytest.fixture
def provider_with_base_url(mock_tools: DomainTools) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="test-key",
        model="claude-sonnet-4-20250514",
        tools=mock_tools,
        base_url="https://custom.api.example.com",
    )


class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_run_simple_response(self, provider: AnthropicProvider) -> None:
        """Test run() with a simple response (no tool use)."""
        # Mock a response with just text, stop_reason=end_turn
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "AAPL looks strong based on fundamentals."

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [mock_text_block]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await provider.run_with_system(
                system_prompt="You are a test analyst.",
                user_prompt="Analyze AAPL",
                agent_name="test",
            )

        assert "AAPL" in result.summary
        assert result.agent_name == "test"

    @pytest.mark.asyncio
    async def test_run_with_tool_use(
        self, provider: AnthropicProvider, mock_tools: DomainTools
    ) -> None:
        """Test run() with a tool use round followed by final response."""
        # First response: tool_use
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "tool_123"
        mock_tool_block.name = "get_stock_quote"
        mock_tool_block.input = {"ticker": "AAPL"}

        mock_response_1 = MagicMock()
        mock_response_1.stop_reason = "tool_use"
        mock_response_1.content = [mock_tool_block]

        # Second response: end_turn with text
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Based on the data, AAPL is trading at $175.50."

        mock_response_2 = MagicMock()
        mock_response_2.stop_reason = "end_turn"
        mock_response_2.content = [mock_text_block]

        with patch.object(
            provider._client.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=[mock_response_1, mock_response_2],
        ):
            result = await provider.run_with_system(
                system_prompt="You are a test analyst.",
                user_prompt="Analyze AAPL",
                agent_name="test",
            )

        assert "175.50" in result.summary
        mock_tools.dispatch.assert_awaited_once_with("get_stock_quote", {"ticker": "AAPL"})
        assert len(result.reasoning_steps) >= 1  # Tool call recorded

    @pytest.mark.asyncio
    async def test_run_protocol_method(self, provider: AnthropicProvider) -> None:
        """Test that run() works via the protocol interface."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Analysis complete."

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [mock_text_block]

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_response
        ):
            task = TaskRequest(prompt="Analyze AAPL", tickers=["AAPL"])
            result = await provider.run(task)

        assert result.summary == "Analysis complete."


class TestAnthropicProviderBaseUrl:
    def test_default_base_url_uses_sdk_default(self, provider: AnthropicProvider) -> None:
        """When no base_url is given, the SDK default is used."""
        # SDK default base_url contains "anthropic.com"
        assert "anthropic.com" in str(provider._client.base_url)

    def test_custom_base_url(self, provider_with_base_url: AnthropicProvider) -> None:
        """When base_url is provided, the client uses it."""
        assert "custom.api.example.com" in str(provider_with_base_url._client.base_url)


class TestToolSchemas:
    def test_schemas_are_valid(self) -> None:
        from superinvestor.agents.tools import TOOL_SCHEMAS

        assert len(TOOL_SCHEMAS) == 12
        for schema in TOOL_SCHEMAS:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema
            assert schema["input_schema"]["type"] == "object"


class TestPrompts:
    def test_all_prompts_loaded(self) -> None:
        from superinvestor.agents.prompts import ANALYST_PROMPTS

        assert AnalystRole.FUNDAMENTAL in ANALYST_PROMPTS
        assert AnalystRole.TECHNICAL in ANALYST_PROMPTS
        assert AnalystRole.SENTIMENT in ANALYST_PROMPTS
        assert AnalystRole.SYNTHESIZER in ANALYST_PROMPTS

        for role, prompt in ANALYST_PROMPTS.items():
            assert len(prompt) > 100, f"Prompt for {role} is too short"
