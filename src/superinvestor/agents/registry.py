from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from superinvestor.agents.providers.anthropic import AnthropicProvider
from superinvestor.agents.tools import DomainTools
from superinvestor.config import Settings
from superinvestor.data.edgar import EdgarProvider
from superinvestor.data.fred import FredProvider
from superinvestor.data.polygon import PolygonProvider
from superinvestor.models.enums import ProviderName

# Optional providers — only available when the 'openai' package is installed.
try:
    from superinvestor.agents.providers.openrouter import OpenRouterProvider
except ImportError:
    OpenRouterProvider = None  # type: ignore[misc,assignment]

try:
    from superinvestor.agents.providers.deepinfra import DeepInfraProvider
except ImportError:
    DeepInfraProvider = None  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from superinvestor.agents.providers.openrouter import OpenRouterProvider
    from superinvestor.agents.providers.deepinfra import DeepInfraProvider


@dataclass
class DataStack:
    """Holds all data providers and the agent provider for lifecycle management.

    Call :meth:`close` to cleanly shut down all HTTP clients.
    """

    polygon: PolygonProvider
    edgar: EdgarProvider
    fred: FredProvider
    tools: DomainTools
    provider: AnthropicProvider | OpenRouterProvider | DeepInfraProvider  # type: ignore[type-arg]

    async def close(self) -> None:
        """Shut down all data-provider HTTP clients."""
        await self.polygon.close()
        await self.edgar.close()
        await self.fred.close()


async def create_provider(
    settings: Settings | None = None,
) -> AnthropicProvider | OpenRouterProvider | DeepInfraProvider:  # type: ignore[type-arg]
    """Create and return the configured agent provider.

    Instantiates the data providers and wires them into ``DomainTools``,
    then builds the appropriate provider on top.

    For callers that also need to manage the provider lifecycle (e.g. to
    close HTTP clients on shutdown), use :func:`create_stack` instead.
    """
    stack = create_stack(settings)
    return stack.provider


def create_stack(settings: Settings | None = None) -> DataStack:
    """Create the full data stack including all providers.

    Returns a :class:`DataStack` whose ``.provider`` attribute is the
    ready-to-use agent provider.  The caller is responsible for calling
    ``await stack.close()`` when done.
    """
    s = settings or Settings()

    polygon = PolygonProvider(
        api_key=s.polygon_api_key,
        rate_limit=s.polygon_rate_limit,
    )
    edgar = EdgarProvider(rate_limit=s.edgar_rate_limit)
    fred = FredProvider(api_key=s.fred_api_key, rate_limit=s.fred_rate_limit)
    tools = DomainTools(polygon=polygon, edgar=edgar, fred=fred, db_path=s.db_path)

    if s.provider == ProviderName.CLAUDE:
        if not s.anthropic_api_key:
            raise ValueError(
                "Anthropic API key is not set. "
                "Run 'superinvestor configure' to set it up, or set the "
                "SUPERINVESTOR_ANTHROPIC_API_KEY environment variable."
            )
        provider: AnthropicProvider | OpenRouterProvider | DeepInfraProvider = AnthropicProvider(  # type: ignore[type-arg]
            api_key=s.anthropic_api_key,
            model=s.claude_model,
            tools=tools,
            base_url=s.anthropic_base_url,
        )

    elif s.provider == ProviderName.OPENROUTER:
        if OpenRouterProvider is None:
            raise ValueError(
                "OpenRouter support requires the 'openai' package. "
                "Install it with: pip install superinvestor-ai[openrouter]"
            )
        if not s.openrouter_api_key:
            raise ValueError(
                "OpenRouter API key is not set. "
                "Run 'superinvestor configure' to set it up, or set the "
                "SUPERINVESTOR_OPENROUTER_API_KEY environment variable."
            )
        provider = OpenRouterProvider(
            api_key=s.openrouter_api_key,
            model=s.openrouter_model,
            tools=tools,
            base_url=s.openrouter_base_url,
        )

    elif s.provider == ProviderName.DEEPINFRA:
        if DeepInfraProvider is None:
            raise ValueError(
                "DeepInfra support requires the 'openai' package. "
                "Install it with: pip install superinvestor-ai[openrouter]"
            )
        if not s.deepinfra_api_key:
            raise ValueError(
                "DeepInfra API key is not set. "
                "Run 'superinvestor configure' to set it up, or set the "
                "SUPERINVESTOR_DEEPINFRA_API_KEY environment variable."
            )
        provider = DeepInfraProvider(
            api_key=s.deepinfra_api_key,
            model=s.deepinfra_model,
            tools=tools,
            base_url=s.deepinfra_base_url,
        )

    else:
        raise ValueError(
            f"Unsupported provider: {s.provider!r}. "
            f"Supported providers: {ProviderName.CLAUDE!r}, {ProviderName.OPENROUTER!r}, "
            f"{ProviderName.DEEPINFRA!r}."
        )

    return DataStack(
        polygon=polygon,
        edgar=edgar,
        fred=fred,
        tools=tools,
        provider=provider,
    )
