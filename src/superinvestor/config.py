from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from superinvestor.models.enums import ProviderName

CONFIG_DIR = Path.home() / ".config" / "superinvestor"
CONFIG_PATH = CONFIG_DIR / "config.toml"

CONFIG_TEMPLATE = """\
# superinvestor configuration
# Uncomment and set values below. Environment variables (SUPERINVESTOR_*)
# take precedence over values in this file.

# -- AI Provider --
# provider = "CLAUDE"
# anthropic_api_key = ""
# anthropic_base_url = ""
# claude_model = "claude-sonnet-4-20250514"
# openai_api_key = ""
# openai_model = "gpt-4o"
# google_api_key = ""
# google_model = "gemini-2.0-flash"
# openrouter_api_key = ""
# openrouter_model = "anthropic/claude-sonnet-4"
# openrouter_base_url = "https://openrouter.ai/api/v1"
# deepinfra_api_key = ""
# deepinfra_model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
# deepinfra_base_url = "https://api.deepinfra.com/v1/openai"

# -- Data Sources --
# polygon_api_key = ""
# fred_api_key = ""

# -- Rate Limits --
# polygon_rate_limit = 5
# edgar_rate_limit = 10
# fred_rate_limit = 120
# cache_ttl_seconds = 300

# -- Database --
# db_path = "superinvestor.db"

# -- Paper Trading --
# paper_initial_cash = 100000

# -- Monitoring --
# monitor_enabled = false
# monitor_interval_minutes = 15
"""


def ensure_config() -> bool:
    """Create the config directory and template file if they don't exist.

    Returns ``True`` if the file was created, ``False`` if it already existed.
    """
    if CONFIG_PATH.exists():
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(CONFIG_TEMPLATE)
    return True


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All variables are prefixed with ``SUPERINVESTOR_``. For example,
    ``anthropic_api_key`` maps to ``SUPERINVESTOR_ANTHROPIC_API_KEY``.
    A ``.env`` file in the working directory is also loaded if present.
    A TOML config file at ``~/.config/superinvestor/config.toml`` is
    also read (env vars take precedence).
    """

    model_config = SettingsConfigDict(
        env_prefix="SUPERINVESTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        toml_file=CONFIG_PATH,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
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
    openrouter_api_key: str = ""
    deepinfra_api_key: str = ""
    polygon_api_key: str = ""
    fred_api_key: str = ""

    # Model selection
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    google_model: str = "gemini-2.0-flash"
    openrouter_model: str = "anthropic/claude-sonnet-4"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    deepinfra_model: str = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"

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
