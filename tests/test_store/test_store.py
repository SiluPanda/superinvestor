from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from superinvestor.models.enums import (
    AlertPriority,
    Exchange,
    FilingType,
    HoldingChangeType,
    SignalSource,
    SignalStrength,
)
from superinvestor.models.market import Stock
from superinvestor.models.filings import Filing
from superinvestor.models.holdings import (
    SuperInvestorProfile,
    Holding13F,
    HoldingChange,
)
from superinvestor.models.thesis import InvestmentThesis
from superinvestor.models.signals import Signal, Alert
from superinvestor.models.analysis import AnalysisResult
from superinvestor.models.portfolio import Portfolio, Position
from superinvestor.models.watchlist import WatchlistItem
from superinvestor.models.market import OHLCV
from superinvestor.models.enums import Timespan
from superinvestor.store.market_store import OHLCVStore, StockStore
from superinvestor.store.filing_store import FilingStore
from superinvestor.store.holdings_store import (
    SuperInvestorStore,
    Holdings13FStore,
    HoldingChangeStore,
)
from superinvestor.store.thesis_store import ThesisStore
from superinvestor.store.signal_store import SignalStore, AlertStore
from superinvestor.store.analysis_store import AnalysisStore
from superinvestor.store.portfolio_store import (
    PortfolioStore,
    PositionStore,
)
from superinvestor.store.watchlist_store import WatchlistStore
from superinvestor.store.cache_store import CacheStore


class TestStockStore:
    @pytest.mark.asyncio
    async def test_insert_and_get_by_ticker(self, db) -> None:
        store = StockStore(db)
        stock = Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ)
        await store.insert(stock)

        got = await store.get_by_ticker("AAPL")
        assert got is not None
        assert got.ticker == "AAPL"
        assert got.name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_get_by_ticker_not_found(self, db) -> None:
        store = StockStore(db)
        got = await store.get_by_ticker("ZZZZ")
        assert got is None

    @pytest.mark.asyncio
    async def test_search(self, db) -> None:
        store = StockStore(db)
        await store.insert(Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ))
        await store.insert(Stock(ticker="AMZN", name="Amazon.com Inc.", exchange=Exchange.NASDAQ))
        await store.insert(Stock(ticker="MSFT", name="Microsoft Corp", exchange=Exchange.NASDAQ))

        results = await store.search("app")
        assert len(results) >= 1
        assert any(s.ticker == "AAPL" for s in results)

    @pytest.mark.asyncio
    async def test_insert_many(self, db) -> None:
        store = StockStore(db)
        stocks = [
            Stock(ticker="A", name="A Inc.", exchange=Exchange.NYSE),
            Stock(ticker="B", name="B Inc.", exchange=Exchange.NYSE),
            Stock(ticker="C", name="C Inc.", exchange=Exchange.NYSE),
        ]
        await store.insert_many(stocks)
        assert await store.count() == 3


class TestFilingStore:
    @pytest.mark.asyncio
    async def test_insert_and_query(self, db) -> None:
        store = FilingStore(db)
        filing = Filing(
            cik="0000320193",
            ticker="AAPL",
            company_name="Apple Inc.",
            filing_type=FilingType.TEN_K,
            accession_number="0000320193-24-000123",
            filed_date=date(2024, 11, 1),
            primary_doc_url="https://sec.gov/filing",
        )
        await store.insert(filing)

        results = await store.get_by_ticker("AAPL")
        assert len(results) == 1
        assert results[0].filing_type == FilingType.TEN_K

    @pytest.mark.asyncio
    async def test_get_by_accession(self, db) -> None:
        store = FilingStore(db)
        filing = Filing(
            cik="0000320193",
            ticker="AAPL",
            company_name="Apple Inc.",
            filing_type=FilingType.EIGHT_K,
            accession_number="unique-acc-123",
            filed_date=date(2024, 11, 1),
            primary_doc_url="https://sec.gov/filing",
        )
        await store.insert(filing)

        got = await store.get_by_accession("unique-acc-123")
        assert got is not None
        assert got.ticker == "AAPL"


class TestHoldingsStore:
    @pytest.mark.asyncio
    async def test_superinvestor_crud(self, db) -> None:
        store = SuperInvestorStore(db)
        profile = SuperInvestorProfile(
            cik="0001067983",
            name="BERKSHIRE HATHAWAY INC",
            short_name="Berkshire",
            manager_name="Warren Buffett",
            aum=Decimal("350000000000"),
        )
        await store.insert(profile)

        got = await store.get_by_cik("0001067983")
        assert got is not None
        assert got.manager_name == "Warren Buffett"

    @pytest.mark.asyncio
    async def test_holdings_13f(self, db) -> None:
        # Must create parent investor first (FK constraint)
        inv_store = SuperInvestorStore(db)
        profile = SuperInvestorProfile(id="inv-1", cik="0001067983", name="BERKSHIRE HATHAWAY INC")
        await inv_store.insert(profile)

        store = Holdings13FStore(db)
        holding = Holding13F(
            investor_id="inv-1",
            filing_accession="acc-1",
            report_date=date(2024, 9, 30),
            ticker="AAPL",
            company_name="Apple Inc.",
            cusip="037833100",
            value_usd=Decimal("84200000"),
            shares=905000000,
        )
        await store.insert(holding)

        results = await store.get_by_investor_and_date("inv-1", date(2024, 9, 30))
        assert len(results) == 1
        assert results[0].shares == 905000000

    @pytest.mark.asyncio
    async def test_holding_changes(self, db) -> None:
        store = HoldingChangeStore(db)
        change = HoldingChange(
            investor_id="inv-1",
            ticker="AAPL",
            report_date=date(2024, 9, 30),
            change_type=HoldingChangeType.INCREASED,
            shares_before=800000000,
            shares_after=905000000,
            shares_change=105000000,
            shares_change_pct=Decimal("13.13"),
        )
        await store.insert(change)

        results = await store.get_by_ticker("AAPL")
        assert len(results) == 1
        assert results[0].change_type == HoldingChangeType.INCREASED


class TestThesisStore:
    @pytest.mark.asyncio
    async def test_thesis_with_lists(self, db) -> None:
        store = ThesisStore(db)
        thesis = InvestmentThesis(
            ticker="AAPL",
            title="Apple AI Play",
            bull_case="Services growth",
            bear_case="Hardware saturation",
            catalysts=["WWDC", "India"],
            risks=["China", "Antitrust"],
            confidence_score=0.8,
        )
        await store.insert(thesis)

        results = await store.get_active("AAPL")
        assert len(results) == 1
        assert results[0].catalysts == ["WWDC", "India"]
        assert results[0].risks == ["China", "Antitrust"]
        assert results[0].confidence_score == 0.8


class TestSignalStore:
    @pytest.mark.asyncio
    async def test_signal_crud(self, db) -> None:
        store = SignalStore(db)
        signal = Signal(
            ticker="AAPL",
            source=SignalSource.THIRTEENF_CHANGE,
            strength=SignalStrength.BUY,
            title="Buffett increases AAPL",
            description="13F shows 11% increase",
            evidence=["Q3 13F filing"],
            confidence=0.85,
        )
        await store.insert(signal)

        results = await store.get_recent("AAPL")
        assert len(results) == 1
        assert results[0].evidence == ["Q3 13F filing"]

    @pytest.mark.asyncio
    async def test_alert_unread(self, db) -> None:
        store = AlertStore(db)
        alert = Alert(
            ticker="AAPL",
            priority=AlertPriority.HIGH,
            title="New 8-K filing",
            message="Apple filed an 8-K",
        )
        await store.insert(alert)

        unread = await store.get_unread()
        assert len(unread) == 1

        await store.mark_read(alert.id)
        unread = await store.get_unread()
        assert len(unread) == 0


class TestPortfolioStore:
    @pytest.mark.asyncio
    async def test_portfolio_and_positions(self, db) -> None:
        port_store = PortfolioStore(db)
        pos_store = PositionStore(db)

        portfolio = Portfolio(
            name="Main",
            initial_cash=Decimal("100000"),
            cash=Decimal("82450"),
        )
        await port_store.insert(portfolio)

        position = Position(
            portfolio_id=portfolio.id,
            ticker="AAPL",
            shares=Decimal("100"),
            avg_cost_basis=Decimal("175.50"),
            current_price=Decimal("180.00"),
            market_value=Decimal("18000"),
            unrealized_pnl=Decimal("450"),
            unrealized_pnl_pct=Decimal("2.56"),
        )
        await pos_store.insert(position)

        positions = await pos_store.get_for_portfolio(portfolio.id)
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].unrealized_pnl == Decimal("450")


class TestWatchlistStore:
    @pytest.mark.asyncio
    async def test_watchlist_crud(self, db) -> None:
        store = WatchlistStore(db)
        item = WatchlistItem(ticker="AAPL", notes="Core", tags=["tech"])
        await store.insert(item)

        assert await store.exists("AAPL") is True
        assert await store.exists("ZZZZ") is False

        all_items = await store.get_all()
        assert len(all_items) == 1
        assert all_items[0].tags == ["tech"]


class TestCacheStore:
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, db) -> None:
        store = CacheStore(db)
        await store.set("test-key", "polygon", '{"price": 175.50}', ttl=300)

        got = await store.get("test-key")
        assert got is not None
        assert got == '{"price": 175.50}'

    @pytest.mark.asyncio
    async def test_cache_miss(self, db) -> None:
        store = CacheStore(db)
        got = await store.get("nonexistent")
        assert got is None

    @pytest.mark.asyncio
    async def test_cache_clear_all(self, db) -> None:
        store = CacheStore(db)
        await store.set("k1", "polygon", "data1", ttl=300)
        await store.set("k2", "edgar", "data2", ttl=300)
        await store.clear_all()
        assert await store.get("k1") is None
        assert await store.get("k2") is None


class TestBaseStoreCRUD:
    @pytest.mark.asyncio
    async def test_update_by_id(self, db) -> None:
        store = StockStore(db)
        stock = Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ)
        await store.insert(stock)

        updated = await store.update_by_id(stock.id, sector="Technology")
        assert updated is True

        got = await store.get_by_id(stock.id)
        assert got is not None
        assert got.sector == "Technology"

    @pytest.mark.asyncio
    async def test_delete_by_id(self, db) -> None:
        store = StockStore(db)
        stock = Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ)
        await store.insert(stock)

        deleted = await store.delete_by_id(stock.id)
        assert deleted is True
        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db) -> None:
        store = StockStore(db)
        deleted = await store.delete_by_id("nonexistent-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_update_by_id_refreshes_updated_at(self, db) -> None:
        store = StockStore(db)
        stock = Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ)
        await store.insert(stock)
        original = (await store.get_by_id(stock.id)).updated_at

        await asyncio.sleep(0.01)
        await store.update_by_id(stock.id, sector="Technology")

        got = await store.get_by_id(stock.id)
        assert got.updated_at > original


class TestOHLCVStore:
    @pytest.mark.asyncio
    async def test_get_range_includes_end_date(self, db) -> None:
        store = OHLCVStore(db)
        bar = OHLCV(
            ticker="AAPL",
            timestamp=datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc),
            timespan=Timespan.DAY,
            open=Decimal("175"),
            high=Decimal("177"),
            low=Decimal("174"),
            close=Decimal("176"),
            volume=50000000,
        )
        await store.insert(bar)

        results = await store.get_range(
            ticker="AAPL",
            start=date(2024, 1, 15),
            end=date(2024, 1, 15),
            timespan="day",
        )
        assert len(results) == 1
        assert results[0].ticker == "AAPL"


class TestAnalysisStore:
    @pytest.mark.asyncio
    async def test_insert_and_get_recent(self, db) -> None:
        store = AnalysisStore(db)
        result = AnalysisResult(
            ticker="AAPL",
            analysis_type="multi_agent",
            title="Analysis of AAPL",
            summary="Apple looks strong",
            details="Full analysis text here",
            confidence=0.0,
        )
        await store.insert(result)

        recent = await store.get_recent("AAPL")
        assert len(recent) == 1
        assert recent[0].ticker == "AAPL"
        assert recent[0].summary == "Apple looks strong"
