# Superinvestor

> v0.3.0-alpha — AI-powered quantitative trading agent harness for US equities.

## Features

- **Multi-analyst pipeline** — parallel AI agents (fundamental, technical, sentiment) analyze stocks independently, then a synthesizer produces a final recommendation
- **Multiple data sources** — Polygon.io (market data), SEC EDGAR (filings, 13F holdings, free), FRED (economic indicators)
- **CLI and TUI** — stream analysis from the command line or explore interactively in the terminal UI
- **Pluggable AI providers** — Anthropic Claude (default), OpenRouter, and DeepInfra
- **MCP support** — integrate external tool servers via the Model Context Protocol
- **Async-first** — built on httpx, aiosqlite, and Pydantic for fast, typed, concurrent workflows

## Installation

```bash
pip install superinvestor
```

For development:

```bash
git clone https://github.com/SiluPanda/superinvestor.git
cd superinvestor
uv sync --all-extras
```

Requires Python 3.12+.

## Quick Start

**1. Create and open the config file:**

```bash
superinvestor configure
```

This creates `~/.config/superinvestor/config.toml` and opens it in your `$EDITOR`. Add your API keys there.

**2. Run an analysis:**

```bash
superinvestor analyze AAPL --stream
```

**3. Or launch the interactive terminal UI:**

```bash
superinvestor tui
```

### Required API Keys

| Key | Where to get it | Required? |
|---|---|---|
| `SUPERINVESTOR_ANTHROPIC_API_KEY` | console.anthropic.com | Yes (default provider) |
| `SUPERINVESTOR_POLYGON_API_KEY` | polygon.io | Yes |
| `SUPERINVESTOR_FRED_API_KEY` | fred.stlouisfed.org | Optional |

SEC EDGAR data is free and requires no API key.

## Commands

| Command | Description |
|---|---|
| `superinvestor analyze TICKER [--stream/-s]` | Run multi-agent analysis on a stock |
| `superinvestor configure` | Open config file in `$EDITOR` |
| `superinvestor tui` | Launch the terminal UI |
| `superinvestor watch TICKER...` | *(planned)* Add tickers to watchlist |
| `superinvestor portfolio` | *(planned)* Show paper trading portfolio |
| `superinvestor monitor` | *(planned)* Start 24/7 monitoring daemon |

Running `superinvestor` with no arguments also launches the TUI.

## Configuration

Settings are loaded in this order (highest precedence first):

1. Environment variables (`SUPERINVESTOR_*`)
2. `.env` file in the working directory
3. `~/.config/superinvestor/config.toml`

Run `superinvestor configure` to create and edit the TOML file. Full template:

```toml
# -- AI Provider --
# provider = "CLAUDE"              # CLAUDE | OPENROUTER | DEEPINFRA
# anthropic_api_key = ""
# anthropic_base_url = ""
# claude_model = "claude-sonnet-4-20250514"
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
# polygon_rate_limit = 5           # calls per minute (free tier)
# edgar_rate_limit = 10            # calls per second (SEC fair-use)
# fred_rate_limit = 120            # calls per minute
# cache_ttl_seconds = 300          # API response cache TTL

# -- Database --
# db_path = "superinvestor.db"

# -- Paper Trading --
# paper_initial_cash = 100000

# -- Monitoring --
# monitor_enabled = false
# monitor_interval_minutes = 15
```

## AI Providers

### Claude (default)

```toml
provider = "CLAUDE"
anthropic_api_key = "sk-ant-..."
# claude_model = "claude-sonnet-4-20250514"
```

### OpenRouter

Routes requests through [OpenRouter](https://openrouter.ai), giving access to many models via a single API.

```toml
provider = "OPENROUTER"
openrouter_api_key = "sk-or-..."
# openrouter_model = "anthropic/claude-sonnet-4"
```

### DeepInfra

Open-source models hosted on [DeepInfra](https://deepinfra.com).

```toml
provider = "DEEPINFRA"
deepinfra_api_key = "..."
# deepinfra_model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
```

## Architecture

```
CLI / TUI
    |
    v
Orchestrator (engine/pipeline.py)
    |
    +---> Fundamental Analyst (AI agent + tools)
    +---> Technical Analyst   (AI agent + tools)
    +---> Sentiment Analyst   (AI agent + tools)
    |
    v
Synthesizer -- merges analyst outputs into a final recommendation
    |
    v
SQLite (analysis history, cached data)

TUI ChatSession
    |
    +---> McpManager -- stdio MCP server(s) for additional tools
```

Each analyst runs as an independent AI agent with access to 12 domain-specific tools covering market data (Polygon.io), SEC filings (EDGAR), and economic indicators (FRED). The orchestrator dispatches them in parallel and collects their reports. The synthesizer weighs all perspectives and produces a single, structured recommendation.

## Development

```bash
# Run tests
uv run pytest

# Type checking
uv run pyright

# Lint and format
uv run ruff check .
uv run ruff format .
```

## License

[MIT](LICENSE)
