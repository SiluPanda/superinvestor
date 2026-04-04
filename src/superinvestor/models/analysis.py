from __future__ import annotations

from pydantic import Field

from .base import SuperInvestorBase


class ReasoningStep(SuperInvestorBase):
    analysis_id: str
    step_number: int
    action: str
    input_summary: str
    output_summary: str
    data_refs: list[str] = Field(default_factory=list)
    duration_ms: int


class AnalysisResult(SuperInvestorBase):
    ticker: str
    analysis_type: str
    title: str
    summary: str
    details: str
    signals_generated: list[str] = Field(default_factory=list)
    confidence: float
