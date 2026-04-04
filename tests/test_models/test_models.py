from __future__ import annotations

from datetime import date, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from superinvestor.models.base import SuperInvestorBase, new_id, utc_now
from superinvestor.models.enums import (
    Exchange,
    FilingType,
    HoldingChangeType,
    SignalSource,
    SignalStrength,
    ThesisStatus,
    TradeAction,
)
from superinvestor.models.market import Stock, Quote, CompanyNews
from superinvestor.models.filings import Filing, FilingDiff
from superinvestor.models.holdings import (
    SuperInvestorProfile,
    HoldingChange,
)
from superinvestor.models.thesis import InvestmentThesis
from superinvestor.models.signals import Signal
from superinvestor.models.portfolio import Portfolio, Trade
from superinvestor.models.agent import AgentEvent, TaskRequest, TaskResult
from superinvestor.models.enums import EventKind, AnalystRole


class TestBase:
    def test_new_id_is_uuid(self) -> None:
        id1 = new_id()
        id2 = new_id()
        assert isinstance(id1, str)
        assert len(id1) == 36  # UUID format
        assert id1 != id2

    def test_utc_now_is_utc(self) -> None:
        now = utc_now()
        assert now.tzinfo == timezone.utc

    def test_base_model_auto_fields(self) -> None:
        class Dummy(SuperInvestorBase):
            name: str

        d = Dummy(name="test")
        assert len(d.id) == 36
        assert d.created_at.tzinfo == timezone.utc
        assert d.updated_at.tzinfo == timezone.utc

    def test_base_model_is_frozen(self) -> None:
        class Dummy(SuperInvestorBase):
            name: str

        d = Dummy(name="test")
        with pytest.raises(ValidationError):
            d.name = "other"  # type: ignore[misc]


class TestMarketModels:
    def test_stock_minimal(self) -> None:
        s = Stock(ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ)
        assert s.ticker == "AAPL"
        assert s.market_cap == Decimal("0")
        assert s.active is True

    def test_stock_full(self) -> None:
        s = Stock(
            ticker="MSFT",
            name="Microsoft Corp",
            exchange=Exchange.NASDAQ,
            sector="Technology",
            industry="Software",
            market_cap=Decimal("3100000000000"),
            shares_outstanding=Decimal("7430000000"),
            cik="0000789019",
        )
        assert s.market_cap == Decimal("3100000000000")

    def test_quote(self) -> None:
        q = Quote(
            ticker="AAPL",
            price=Decimal("175.50"),
            change=Decimal("2.30"),
            change_percent=Decimal("1.33"),
            open=Decimal("173.20"),
            high=Decimal("176.00"),
            low=Decimal("172.80"),
            previous_close=Decimal("173.20"),
            volume=50000000,
            timestamp=utc_now(),
        )
        assert q.price == Decimal("175.50")

    def test_company_news_optional_sentiment(self) -> None:
        n = CompanyNews(
            ticker="AAPL",
            headline="Apple launches new product",
            summary="Details...",
            source="Reuters",
            url="https://example.com",
            published_at=utc_now(),
            category="product",
        )
        assert n.sentiment_score is None


class TestFilingModels:
    def test_filing(self) -> None:
        f = Filing(
            cik="0000320193",
            ticker="AAPL",
            company_name="Apple Inc.",
            filing_type=FilingType.TEN_K,
            accession_number="0000320193-24-000123",
            filed_date=date(2024, 11, 1),
            primary_doc_url="https://sec.gov/...",
        )
        assert f.filing_type == FilingType.TEN_K

    def test_filing_diff(self) -> None:
        d = FilingDiff(
            filing_id_old="old-id",
            filing_id_new="new-id",
            section_name="Item 1A",
            additions="New risk factor about AI",
            similarity_score=0.85,
        )
        assert d.similarity_score == 0.85


class TestHoldingsModels:
    def test_superinvestor_profile(self) -> None:
        p = SuperInvestorProfile(
            cik="0001067983",
            name="BERKSHIRE HATHAWAY INC",
            short_name="Berkshire Hathaway",
            manager_name="Warren Buffett",
            aum=Decimal("350000000000"),
        )
        assert p.manager_name == "Warren Buffett"

    def test_holding_change(self) -> None:
        hc = HoldingChange(
            investor_id="inv-1",
            ticker="AAPL",
            report_date=date(2024, 9, 30),
            prev_report_date=date(2024, 6, 30),
            change_type=HoldingChangeType.INCREASED,
            shares_before=900000000,
            shares_after=1000000000,
            shares_change=100000000,
            shares_change_pct=Decimal("11.11"),
            portfolio_pct=Decimal("48.5"),
        )
        assert hc.change_type == HoldingChangeType.INCREASED


class TestThesisModels:
    def test_thesis_with_lists(self) -> None:
        t = InvestmentThesis(
            ticker="AAPL",
            title="Apple AI Services Growth",
            bull_case="Services revenue accelerating",
            bear_case="Hardware saturation",
            catalysts=["WWDC AI announcement", "India expansion"],
            risks=["China tensions", "Antitrust"],
            target_price=Decimal("220.00"),
            confidence_score=0.75,
        )
        assert len(t.catalysts) == 2
        assert len(t.risks) == 2
        assert t.confidence_score == 0.75

    def test_thesis_defaults(self) -> None:
        t = InvestmentThesis(
            ticker="X",
            title="Test",
            bull_case="bull",
            bear_case="bear",
        )
        assert t.catalysts == []
        assert t.risks == []
        assert t.status == ThesisStatus.ACTIVE
        assert t.confidence_score == 0.5


class TestPortfolioModels:
    def test_portfolio_is_mutable(self) -> None:
        p = Portfolio(
            name="Main",
            initial_cash=Decimal("100000"),
            cash=Decimal("100000"),
        )
        # Portfolio should NOT be frozen
        p.cash = Decimal("95000")
        assert p.cash == Decimal("95000")

    def test_trade(self) -> None:
        t = Trade(
            portfolio_id="port-1",
            ticker="AAPL",
            action=TradeAction.BUY,
            shares=Decimal("100"),
            price=Decimal("175.50"),
            total_value=Decimal("17550.00"),
        )
        assert t.action == TradeAction.BUY


class TestAgentModels:
    def test_agent_event(self) -> None:
        e = AgentEvent(
            kind=EventKind.TEXT_DELTA,
            agent_name="fundamental",
            content="Analyzing AAPL fundamentals...",
        )
        assert e.tool_name is None

    def test_task_request_defaults(self) -> None:
        r = TaskRequest(prompt="Analyze AAPL", tickers=["AAPL"])
        assert AnalystRole.FUNDAMENTAL in r.analyst_roles
        assert AnalystRole.SYNTHESIZER not in r.analyst_roles

    def test_task_result(self) -> None:
        r = TaskResult(
            summary="AAPL looks strong",
            agent_name="pipeline",
        )
        assert r.reasoning_steps == []
        assert r.signals == []


class TestSignalModels:
    def test_signal(self) -> None:
        s = Signal(
            ticker="AAPL",
            source=SignalSource.THIRTEENF_CHANGE,
            strength=SignalStrength.BUY,
            title="Buffett increases AAPL position",
            description="13F shows 11% increase",
            evidence=["Q3 2024 13F filing"],
            confidence=0.8,
        )
        assert s.strength == SignalStrength.BUY
        assert len(s.evidence) == 1
