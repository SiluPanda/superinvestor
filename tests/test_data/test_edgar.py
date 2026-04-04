from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from superinvestor.data.edgar import EdgarError, EdgarProvider
from superinvestor.models.enums import FilingType


def _mock_response(content: str | dict, status_code: int = 200) -> httpx.Response:
    if isinstance(content, dict):
        return httpx.Response(
            status_code=status_code, json=content, request=httpx.Request("GET", "http://test")
        )
    return httpx.Response(
        status_code=status_code, text=content, request=httpx.Request("GET", "http://test")
    )


@pytest.fixture
def provider() -> EdgarProvider:
    return EdgarProvider(rate_limit=1000)


MOCK_SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-24-000123",
                "0000320193-24-000100",
                "0000320193-24-000050",
            ],
            "form": ["10-K", "10-Q", "8-K"],
            "filingDate": ["2024-11-01", "2024-08-01", "2024-07-15"],
            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm", "aapl-20240715.htm"],
            "primaryDocDescription": ["10-K", "10-Q", "8-K"],
            "reportDate": ["2024-09-28", "2024-06-29", ""],
        }
    },
}

MOCK_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}


class TestLookupCik:
    @pytest.mark.asyncio
    async def test_lookup_cik(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(MOCK_TICKERS),
        ):
            cik = await provider.lookup_cik("AAPL")
        assert cik == "320193"

    @pytest.mark.asyncio
    async def test_lookup_cik_not_found(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(MOCK_TICKERS),
        ):
            with pytest.raises(EdgarError):
                await provider.lookup_cik("ZZZZ")


class TestGetCompanyFilings:
    @pytest.mark.asyncio
    async def test_get_all_filings(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(MOCK_SUBMISSIONS),
        ):
            filings = await provider.get_company_filings("320193")

        assert len(filings) == 3
        assert filings[0].filing_type == FilingType.TEN_K
        assert filings[0].ticker == "AAPL"
        assert filings[0].accession_number == "0000320193-24-000123"

    @pytest.mark.asyncio
    async def test_get_filings_filtered_by_type(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(MOCK_SUBMISSIONS),
        ):
            filings = await provider.get_company_filings("320193", filing_type=FilingType.TEN_K)

        assert len(filings) == 1
        assert filings[0].filing_type == FilingType.TEN_K

    @pytest.mark.asyncio
    async def test_get_filings_limit(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(MOCK_SUBMISSIONS),
        ):
            filings = await provider.get_company_filings("320193", limit=2)
        assert len(filings) == 2


class TestGetFilingText:
    @pytest.mark.asyncio
    async def test_get_filing_text(self, provider: EdgarProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response("<html>Filing content</html>"),
        ):
            text = await provider.get_filing_text("https://sec.gov/some/filing.htm")
        assert "Filing content" in text


class TestSearchFilings:
    @pytest.mark.asyncio
    async def test_search(self, provider: EdgarProvider) -> None:
        mock_search = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "file_date": "2024-11-01",
                            "form_type": "10-K",
                            "entity_name": "Apple Inc.",
                            "file_num": "001-36743",
                            "period_of_report": "2024-09-28",
                        },
                        "_id": "0000320193-24-000123",
                    }
                ]
            }
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_search),
        ):
            results = await provider.search_filings("Apple revenue growth")
        assert len(results) == 1
        assert results[0].cik == ""
        assert results[0].accession_number == "0000320193-24-000123"


class TestGetInsiderTrades:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self, provider: EdgarProvider) -> None:
        """Insider trades are not yet implemented; should return empty, not fabricated data."""
        trades = await provider.get_insider_trades("320193")
        assert trades == []


class TestParse13fXml:
    def test_uses_provided_report_date(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <informationTable xmlns="http://www.sec.gov/Archives/edgar/xbrlcf/13f">
            <infoTable>
                <nameOfIssuer>APPLE INC</nameOfIssuer>
                <cusip>037833100</cusip>
                <value>84200</value>
                <shrsOrPrnAmt>
                    <sshPrnamt>905000000</sshPrnamt>
                    <sshPrnamtType>SH</sshPrnamtType>
                </shrsOrPrnAmt>
                <investmentDiscretion>SOLE</investmentDiscretion>
            </infoTable>
        </informationTable>"""

        from datetime import date

        report_date = date(2024, 9, 30)
        holdings = EdgarProvider._parse_13f_xml(
            xml,
            investor_id="0001067983",
            accession_number="acc-123",
            report_date=report_date,
        )

        assert len(holdings) == 1
        assert holdings[0].report_date == date(2024, 9, 30)
        assert holdings[0].report_date != date.today()


class TestErrors:
    @pytest.mark.asyncio
    async def test_http_error(self, provider: EdgarProvider) -> None:
        error_resp = httpx.Response(
            500, text="Server Error", request=httpx.Request("GET", "http://test")
        )
        with patch.object(
            provider._client, "request", new_callable=AsyncMock, return_value=error_resp
        ):
            with pytest.raises(EdgarError) as exc_info:
                await provider.get_company_filings("320193")
            assert exc_info.value.status_code == 500
