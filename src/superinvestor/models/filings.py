from __future__ import annotations

from datetime import date

from .base import SuperInvestorBase
from .enums import FilingType


class Filing(SuperInvestorBase):
    cik: str
    ticker: str
    company_name: str
    filing_type: FilingType
    accession_number: str
    filed_date: date
    period_of_report: date | None = None
    primary_doc_url: str
    filing_index_url: str = ""


class FilingSection(SuperInvestorBase):
    filing_id: str
    section_name: str
    section_title: str
    content: str
    word_count: int = 0
    order_index: int = 0


class FilingDiff(SuperInvestorBase):
    filing_id_old: str
    filing_id_new: str
    section_name: str
    additions: str = ""
    deletions: str = ""
    similarity_score: float = 0.0
