from __future__ import annotations

from superinvestor.agents.providers.openrouter import OpenRouterProvider
from superinvestor.agents.tools import DomainTools

_DEFAULT_BASE_URL = "https://api.deepinfra.com/v1/openai"


class DeepInfraProvider(OpenRouterProvider):
    """Agent provider backed by DeepInfra (OpenAI-compatible API).

    DeepInfra uses the same OpenAI chat completions format as OpenRouter,
    so this subclass only overrides the default base URL.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        tools: DomainTools,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        super().__init__(api_key=api_key, model=model, tools=tools, base_url=base_url)
