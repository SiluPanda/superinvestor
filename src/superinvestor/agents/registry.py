from __future__ import annotations

from dataclasses import dataclass

from superinvestor.agents.providers.anthropic import AnthropicProvider
from superinvestor.agents.tools import DomainTools
from superinvestor.config import Settings
from superinvestor.data.edgar import EdgarProvider
from superinvestor.data.fred import FredProvider
from superinvestor.data.polygon import PolygonProvider
from superinvestor.models.enums import ProviderName


@dataclass
class DataStack:
    """Holds all data providers and the agent provider for lifecycle management.

    Call :meth:`close` to cleanly shut down all HTTP clients.
    """

    polygon: PolygonProvider
    edgar: EdgarProvider
    fred: FredProvider
    tools: DomainTools
    provider: AnthropicProvider

    async def close(self) -> None:
        """Shut down all data-provider HTTP clients."""
        await self.polygon.close()
        await self.edgar.close()
        await self.fred.close()


async def create_provider(settings: Settings | None = None) -> AnthropicProvider:
    """Create and return the configured Anthropic agent provider.

    Instantiates the data providers and wires them into ``DomainTools``,
    then builds an :class:`AnthropicProvider` on top.

    For callers that also need to manage the provider lifecycle (e.g. to
    close HTTP clients on shutdown), use :func:`create_stack` instead.
    """
    stack = create_stack(settings)
    return stack.provider


def create_stack(settings: Settings | None = None) -> DataStack:
    """Create the full data stack including all providers.

    Returns a :class:`DataStack` whose ``.provider`` attribute is the
    ready-to-use :class:`AnthropicProvider`.  The caller is responsible
    for calling ``await stack.close()`` when done.
    """
    s = settings or Settings()

    if s.provider != ProviderName.CLAUDE:
        raise ValueError(
            f"Unsupported provider: {s.provider!r}. "
            f"Only {ProviderName.CLAUDE!r} is currently implemented."
        )

    polygon = PolygonProvider(
        api_key=s.polygon_api_key,
        rate_limit=s.polygon_rate_limit,
    )
    edgar = EdgarProvider(rate_limit=s.edgar_rate_limit)
    fred = FredProvider(api_key=s.fred_api_key, rate_limit=s.fred_rate_limit)
    tools = DomainTools(polygon=polygon, edgar=edgar, fred=fred)

    provider = AnthropicProvider(
        api_key=s.anthropic_api_key,
        model=s.claude_model,
        tools=tools,
        base_url=s.anthropic_base_url,
    )

    return DataStack(
        polygon=polygon,
        edgar=edgar,
        fred=fred,
        tools=tools,
        provider=provider,
    )
