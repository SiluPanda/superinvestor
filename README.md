# Superinvestor

AI-powered quantitative trading agent harness for US equities.

## Features

- **Multi-analyst pipeline** -- parallel AI agents (fundamental, technical, sentiment) analyze stocks independently, then a synthesizer produces a final recommendation
- **Multiple data sources** -- Polygon.io (market data), SEC EDGAR (filings, 13F holdings), FRED (economic indicators)
- **CLI and TUI** -- stream analysis from the command line or explore interactively in the terminal UI
- **Pluggable AI providers** -- Anthropic Claude (primary), with optional OpenAI and Google support
- **Async-first** -- built on httpx, aiosqlite, and Pydantic for fast, typed, concurrent workflows

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

## Quick Start

Set the required environment variables:

```bash
export SUPERINVESTOR_ANTHROPIC_API_KEY="sk-ant-..."
export SUPERINVESTOR_POLYGON_API_KEY="..."
export SUPERINVESTOR_FRED_API_KEY="..."
```

Run an analysis:

```bash
superinvestor analyze AAPL --stream
```

Launch the terminal UI:

```bash
superinvestor tui
```

### Optional Configuration

| Variable | Description |
|---|---|
| `SUPERINVESTOR_CLAUDE_MODEL` | Override the default Claude model |
| `SUPERINVESTOR_DB_PATH` | Custom SQLite database path |

## Architecture

```
CLI / TUI
    |
    v
Orchestrator
    |
    +---> Fundamental Analyst (AI agent)
    +---> Technical Analyst   (AI agent)
    +---> Sentiment Analyst   (AI agent)
    |
    v
Synthesizer -- merges analyst outputs into a final recommendation
    |
    v
SQLite (analysis history, cached data)
```

Each analyst runs as an independent AI agent with access to its own data sources. The orchestrator dispatches them in parallel and collects their reports. The synthesizer weighs all perspectives and produces a single, structured recommendation.

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

Requires Python 3.12+.

## License

[MIT](LICENSE)
