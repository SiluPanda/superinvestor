from __future__ import annotations

from enum import StrEnum


class Exchange(StrEnum):
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"


class FilingType(StrEnum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    THIRTEEN_F_HR = "13F-HR"
    FORM_3 = "3"
    FORM_4 = "4"
    FORM_5 = "5"


class SignalStrength(StrEnum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class SignalSource(StrEnum):
    INSIDER_TRADE = "insider_trade"
    THIRTEENF_CHANGE = "13f_change"
    EARNINGS_SURPRISE = "earnings_surprise"
    FILING_ANALYSIS = "filing_analysis"
    TECHNICAL = "technical"
    ECONOMIC = "economic"
    NEWS_SENTIMENT = "news_sentiment"


class TradeAction(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


class InsiderTradeType(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"
    OPTION_EXERCISE = "option_exercise"
    GIFT = "gift"


class HoldingChangeType(StrEnum):
    NEW_POSITION = "new_position"
    INCREASED = "increased"
    DECREASED = "decreased"
    CLOSED = "closed"
    UNCHANGED = "unchanged"


class ThesisStatus(StrEnum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    REALIZED = "realized"
    ARCHIVED = "archived"


class AlertPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Timespan(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalystRole(StrEnum):
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FILING = "filing"
    SUPERINVESTOR = "superinvestor"
    SYNTHESIZER = "synthesizer"


class ProviderName(StrEnum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    DEEPINFRA = "deepinfra"


class EventKind(StrEnum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_SWITCH = "agent_switch"
    DONE = "done"
    ERROR = "error"
