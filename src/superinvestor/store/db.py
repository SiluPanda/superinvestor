from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

MIGRATIONS: list[str] = [
    # Migration 0: schema version table
    """
    CREATE TABLE IF NOT EXISTS _schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );
    """,
    # Migration 1: market data tables
    """
    CREATE TABLE IF NOT EXISTS stocks (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        exchange TEXT NOT NULL,
        sector TEXT NOT NULL,
        industry TEXT NOT NULL,
        market_cap TEXT NOT NULL,
        shares_outstanding TEXT NOT NULL,
        cik TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_stocks_cik ON stocks (cik);

    CREATE TABLE IF NOT EXISTS quotes (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        price TEXT NOT NULL,
        change TEXT NOT NULL,
        change_percent TEXT NOT NULL,
        open TEXT NOT NULL,
        high TEXT NOT NULL,
        low TEXT NOT NULL,
        previous_close TEXT NOT NULL,
        volume INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_quotes_ticker_ts ON quotes (ticker, timestamp DESC);

    CREATE TABLE IF NOT EXISTS ohlcv (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        timespan TEXT NOT NULL,
        open TEXT NOT NULL,
        high TEXT NOT NULL,
        low TEXT NOT NULL,
        close TEXT NOT NULL,
        volume INTEGER NOT NULL,
        vwap TEXT NOT NULL,
        num_trades INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlcv_ticker_timespan_ts
        ON ohlcv (ticker, timespan, timestamp);

    CREATE TABLE IF NOT EXISTS company_news (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        headline TEXT NOT NULL,
        summary TEXT NOT NULL,
        source TEXT NOT NULL,
        url TEXT NOT NULL,
        published_at TEXT NOT NULL,
        category TEXT NOT NULL,
        sentiment_score TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_company_news_ticker ON company_news (ticker);
    CREATE INDEX IF NOT EXISTS idx_company_news_published ON company_news (published_at DESC);

    CREATE TABLE IF NOT EXISTS earnings_events (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        report_date TEXT NOT NULL,
        fiscal_year INTEGER NOT NULL,
        fiscal_quarter INTEGER NOT NULL,
        eps_estimate TEXT,
        eps_actual TEXT,
        revenue_estimate TEXT,
        revenue_actual TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_events (ticker);
    CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_events (report_date DESC);
    """,
    # Migration 2: SEC filings tables
    """
    CREATE TABLE IF NOT EXISTS filings (
        id TEXT PRIMARY KEY,
        cik TEXT NOT NULL,
        ticker TEXT NOT NULL,
        company_name TEXT NOT NULL,
        filing_type TEXT NOT NULL,
        accession_number TEXT NOT NULL UNIQUE,
        filed_date TEXT NOT NULL,
        period_of_report TEXT,
        primary_doc_url TEXT NOT NULL,
        filing_index_url TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings (ticker);
    CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings (cik);
    CREATE INDEX IF NOT EXISTS idx_filings_filed ON filings (filed_date DESC);

    CREATE TABLE IF NOT EXISTS filing_sections (
        id TEXT PRIMARY KEY,
        filing_id TEXT NOT NULL REFERENCES filings(id),
        section_name TEXT NOT NULL,
        section_title TEXT NOT NULL,
        content TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        order_index INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_filing_sections_filing ON filing_sections (filing_id);

    CREATE TABLE IF NOT EXISTS filing_diffs (
        id TEXT PRIMARY KEY,
        filing_id_old TEXT NOT NULL REFERENCES filings(id),
        filing_id_new TEXT NOT NULL REFERENCES filings(id),
        section_name TEXT NOT NULL,
        additions TEXT NOT NULL,
        deletions TEXT NOT NULL,
        similarity_score REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_filing_diffs_new ON filing_diffs (filing_id_new);
    """,
    # Migration 3: holdings tables
    """
    CREATE TABLE IF NOT EXISTS super_investor_profiles (
        id TEXT PRIMARY KEY,
        cik TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        short_name TEXT NOT NULL,
        manager_name TEXT NOT NULL,
        aum TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS holdings_13f (
        id TEXT PRIMARY KEY,
        investor_id TEXT NOT NULL REFERENCES super_investor_profiles(id),
        filing_accession TEXT NOT NULL,
        report_date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        company_name TEXT NOT NULL,
        cusip TEXT NOT NULL,
        value_usd TEXT NOT NULL,
        shares INTEGER NOT NULL,
        share_type TEXT NOT NULL,
        investment_discretion TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_holdings_investor ON holdings_13f (investor_id);
    CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings_13f (ticker);
    CREATE INDEX IF NOT EXISTS idx_holdings_date ON holdings_13f (report_date DESC);

    CREATE TABLE IF NOT EXISTS holding_changes (
        id TEXT PRIMARY KEY,
        investor_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        report_date TEXT NOT NULL,
        prev_report_date TEXT,
        change_type TEXT NOT NULL,
        shares_before INTEGER NOT NULL,
        shares_after INTEGER NOT NULL,
        shares_change INTEGER NOT NULL,
        shares_change_pct TEXT NOT NULL,
        value_before TEXT NOT NULL,
        value_after TEXT NOT NULL,
        portfolio_pct TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_holding_changes_investor ON holding_changes (investor_id);
    CREATE INDEX IF NOT EXISTS idx_holding_changes_ticker ON holding_changes (ticker);

    CREATE TABLE IF NOT EXISTS insider_trades (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        insider_cik TEXT NOT NULL,
        insider_name TEXT NOT NULL,
        insider_title TEXT NOT NULL,
        trade_type TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        shares INTEGER NOT NULL,
        price_per_share TEXT NOT NULL,
        total_value TEXT NOT NULL,
        shares_owned_after INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_insider_trades_ticker ON insider_trades (ticker);
    CREATE INDEX IF NOT EXISTS idx_insider_trades_date ON insider_trades (trade_date DESC);
    """,
    # Migration 4: thesis tables
    """
    CREATE TABLE IF NOT EXISTS investment_theses (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        bull_case TEXT NOT NULL,
        bear_case TEXT NOT NULL,
        catalysts TEXT NOT NULL DEFAULT '[]',
        risks TEXT NOT NULL DEFAULT '[]',
        target_price TEXT,
        entry_price TEXT,
        time_horizon_months INTEGER,
        confidence_score REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_theses_ticker ON investment_theses (ticker);
    CREATE INDEX IF NOT EXISTS idx_theses_status ON investment_theses (status);

    CREATE TABLE IF NOT EXISTS thesis_updates (
        id TEXT PRIMARY KEY,
        thesis_id TEXT NOT NULL REFERENCES investment_theses(id),
        trigger TEXT NOT NULL,
        observation TEXT NOT NULL,
        impact TEXT NOT NULL,
        confidence_delta REAL NOT NULL,
        new_status TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_thesis_updates_thesis ON thesis_updates (thesis_id);
    """,
    # Migration 5: signals tables
    """
    CREATE TABLE IF NOT EXISTS signals (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        source TEXT NOT NULL,
        strength TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        evidence TEXT NOT NULL DEFAULT '[]',
        data_refs TEXT NOT NULL DEFAULT '[]',
        confidence REAL NOT NULL,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals (ticker);
    CREATE INDEX IF NOT EXISTS idx_signals_source ON signals (source);

    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        signal_id TEXT REFERENCES signals(id),
        ticker TEXT NOT NULL,
        priority TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        read INTEGER NOT NULL DEFAULT 0,
        dismissed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts (ticker);
    CREATE INDEX IF NOT EXISTS idx_alerts_read ON alerts (read);
    """,
    # Migration 6: analysis tables
    """
    CREATE TABLE IF NOT EXISTS analysis_results (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        analysis_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        details TEXT NOT NULL,
        signals_generated TEXT NOT NULL DEFAULT '[]',
        confidence REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_analysis_ticker ON analysis_results (ticker);

    CREATE TABLE IF NOT EXISTS reasoning_steps (
        id TEXT PRIMARY KEY,
        analysis_id TEXT NOT NULL REFERENCES analysis_results(id),
        step_number INTEGER NOT NULL,
        action TEXT NOT NULL,
        input_summary TEXT NOT NULL,
        output_summary TEXT NOT NULL,
        data_refs TEXT NOT NULL DEFAULT '[]',
        duration_ms INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_reasoning_analysis ON reasoning_steps (analysis_id);
    """,
    # Migration 7: portfolio tables
    """
    CREATE TABLE IF NOT EXISTS portfolios (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        initial_cash TEXT NOT NULL,
        cash TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL REFERENCES portfolios(id),
        ticker TEXT NOT NULL,
        shares TEXT NOT NULL,
        avg_cost_basis TEXT NOT NULL,
        current_price TEXT NOT NULL,
        market_value TEXT NOT NULL,
        unrealized_pnl TEXT NOT NULL,
        unrealized_pnl_pct TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (portfolio_id, ticker)
    );
    CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions (portfolio_id);

    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL REFERENCES portfolios(id),
        ticker TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        shares TEXT NOT NULL,
        price TEXT NOT NULL,
        total_value TEXT NOT NULL,
        thesis_id TEXT,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_trades_portfolio ON trades (portfolio_id);
    CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades (ticker);

    CREATE TABLE IF NOT EXISTS pnl_snapshots (
        id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL REFERENCES portfolios(id),
        snapshot_date TEXT NOT NULL,
        total_value TEXT NOT NULL,
        cash TEXT NOT NULL,
        invested_value TEXT NOT NULL,
        unrealized_pnl TEXT NOT NULL,
        realized_pnl TEXT NOT NULL,
        daily_return_pct TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (portfolio_id, snapshot_date)
    );
    CREATE INDEX IF NOT EXISTS idx_pnl_portfolio ON pnl_snapshots (portfolio_id);
    """,
    # Migration 8: watchlist + cache
    """
    CREATE TABLE IF NOT EXISTS watchlist_items (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL UNIQUE,
        notes TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        thesis_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS provider_cache (
        cache_key TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        response_data TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        ttl_seconds INTEGER NOT NULL,
        expires_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_cache_expires ON provider_cache (expires_at);
    """,
]


class Database:
    """Manages the SQLite connection lifecycle and schema migrations."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        """Open the database, enable WAL + FK, and run pending migrations."""
        self._conn = await aiosqlite.connect(str(self._path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._run_migrations()
        return self._conn

    async def close(self) -> None:
        """Close the database connection if open."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Return the active connection or raise if not connected."""
        if self._conn is None:
            msg = "Database not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._conn

    async def _run_migrations(self) -> None:
        """Apply any migrations that haven't been run yet."""
        conn = self.conn

        # Ensure the schema version table exists (migration 0 handles this,
        # but we need to bootstrap it for the very first run).
        await conn.executescript(MIGRATIONS[0])

        cursor = await conn.execute("SELECT COALESCE(MAX(version), -1) FROM _schema_version")
        row = await cursor.fetchone()
        current_version: int = row[0] if row else -1

        for version, sql in enumerate(MIGRATIONS):
            if version <= current_version:
                continue
            logger.info("Applying migration %d", version)
            await conn.executescript(sql)
            await conn.execute("INSERT INTO _schema_version (version) VALUES (?)", (version,))

        await conn.commit()
