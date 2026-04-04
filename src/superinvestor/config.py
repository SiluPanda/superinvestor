from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from superinvestor.models.enums import ProviderName


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All variables are prefixed with ``SUPERINVESTOR_``. For example,
    ``anthropic_api_key`` maps to ``SUPERINVESTOR_ANTHROPIC_API_KEY``.
    A ``.env`` file in the working directory is also loaded if present.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUPERINVESTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Database
    db_path: Path = Field(default=Path("superinvestor.db"))

    # AI Provider
    provider: ProviderName = ProviderName.CLAUDE

    # API Keys
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    polygon_api_key: str = ""
    fred_api_key: str = ""

    # Model selection
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    google_model: str = "gemini-2.0-flash"

    # Rate limits per data provider
    polygon_rate_limit: int = 5  # calls per minute (Polygon free tier)
    edgar_rate_limit: int = 10  # calls per second (SEC fair-use policy)
    fred_rate_limit: int = 120  # calls per minute (FRED API limit)
    cache_ttl_seconds: int = 300  # default cache TTL (5 min)

    # Paper trading
    paper_initial_cash: int = 100000  # $100k default

    # Monitoring
    monitor_enabled: bool = False
    monitor_interval_minutes: int = 15
