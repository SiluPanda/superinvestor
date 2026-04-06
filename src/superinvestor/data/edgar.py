from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from superinvestor.data.base import RateLimiter, create_http_client
from superinvestor.models.enums import FilingType
from superinvestor.models.filings import Filing
from superinvestor.models.holdings import Holding13F, InsiderTrade

logger = logging.getLogger(__name__)

_SEC_DATA_BASE = "https://data.sec.gov"
_SEC_EFTS_BASE = "https://efts.sec.gov"
_SEC_WWW_BASE = "https://www.sec.gov"
_COMPANY_TICKERS_URL = f"{_SEC_WWW_BASE}/files/company_tickers.json"


class EdgarError(Exception):
    """Raised when an SEC EDGAR API request fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"EDGAR API error {status_code}: {message}")


class CompanyFact(BaseModel):
    """A single XBRL fact data point (revenue, net income, etc.)."""

    value: Decimal
    end_date: date
    fiscal_year: int
    fiscal_period: str  # "FY", "Q1", "Q2", "Q3", "Q4"
    form: str  # "10-K", "10-Q"
    filed_date: date


def _pad_cik(cik: str) -> str:
    """Zero-pad a CIK to 10 digits."""
    return cik.lstrip("0").zfill(10)


def _strip_accession_dashes(accession: str) -> str:
    """Remove dashes from an accession number for URL paths."""
    return accession.replace("-", "")


def _safe_date(value: str) -> date | None:
    """Parse a YYYY-MM-DD string, returning None on failure."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _filing_type_or_none(form: str) -> FilingType | None:
    """Convert a form string to FilingType, returning None if unrecognised."""
    try:
        return FilingType(form)
    except ValueError:
        return None


class EdgarProvider:
    """Async client for the SEC EDGAR data APIs.

    No API key required.  All requests include a ``User-Agent`` header with
    contact information as required by the SEC fair-access policy.
    """

    def __init__(
        self,
        rate_limit: int = 10,
        user_agent: str = "SuperInvestor/1.0 (superinvestor@example.com)",
    ) -> None:
        headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._client = create_http_client(headers=headers)
        self._limiter = RateLimiter(calls_per_period=rate_limit, period_seconds=1.0)
        # Lazily populated ticker -> CIK mapping.
        self._ticker_cik_map: dict[str, str] | None = None
        self._cik_map_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _get_json(self, url: str) -> dict:
        """Rate-limited GET that returns parsed JSON."""
        await self._limiter.acquire()
        response = await self._client.get(url)
        if response.status_code != 200:
            raise EdgarError(response.status_code, f"GET {url}")
        return response.json()

    async def _get_text(self, url: str) -> str:
        """Rate-limited GET that returns raw text."""
        await self._limiter.acquire()
        response = await self._client.get(url)
        if response.status_code != 200:
            raise EdgarError(response.status_code, f"GET {url}")
        return response.text

    # ------------------------------------------------------------------
    # CIK lookup
    # ------------------------------------------------------------------

    async def lookup_cik(self, ticker: str) -> str:
        """Look up the CIK for a ticker symbol.

        Uses the SEC ``company_tickers.json`` endpoint and caches the
        mapping in memory for subsequent calls.
        """
        async with self._cik_map_lock:
            if self._ticker_cik_map is None:
                data = await self._get_json(_COMPANY_TICKERS_URL)
                mapping: dict[str, str] = {}
                for entry in data.values():
                    t = str(entry.get("ticker", "")).upper()
                    cik_str = str(entry.get("cik_str", ""))
                    if t and cik_str:
                        mapping[t] = cik_str
                self._ticker_cik_map = mapping

        normalised = ticker.strip().upper()
        cik = self._ticker_cik_map.get(normalised)
        if cik is None:
            raise EdgarError(404, f"No CIK found for ticker '{ticker}'")
        return cik

    # ------------------------------------------------------------------
    # Company submissions (filings list)
    # ------------------------------------------------------------------

    async def get_company_filings(
        self,
        cik: str,
        filing_type: FilingType | None = None,
        limit: int = 20,
    ) -> list[Filing]:
        """Get recent filings for a company by CIK."""
        padded = _pad_cik(cik)
        url = f"{_SEC_DATA_BASE}/submissions/CIK{padded}.json"
        data = await self._get_json(url)

        company_name: str = data.get("name", "")
        tickers: list[str] = data.get("tickers", [])
        ticker = tickers[0] if tickers else ""

        recent = data.get("filings", {}).get("recent", {})
        return self._parse_submissions(
            recent,
            cik=padded,
            ticker=ticker,
            company_name=company_name,
            filing_type=filing_type,
            limit=limit,
        )

    def _parse_submissions(
        self,
        recent: dict,
        *,
        cik: str,
        ticker: str,
        company_name: str,
        filing_type: FilingType | None,
        limit: int,
    ) -> list[Filing]:
        """Zip parallel arrays from the submissions response into Filing models."""
        accession_numbers: list[str] = recent.get("accessionNumber", [])
        forms: list[str] = recent.get("form", [])
        filing_dates: list[str] = recent.get("filingDate", [])
        primary_docs: list[str] = recent.get("primaryDocument", [])
        report_dates: list[str] = recent.get("reportDate", [])

        results: list[Filing] = []
        for i in range(len(accession_numbers)):
            form = forms[i] if i < len(forms) else ""
            if filing_type is not None and form != filing_type.value:
                continue

            ft = _filing_type_or_none(form)
            if ft is None:
                continue

            filed = _safe_date(filing_dates[i] if i < len(filing_dates) else "")
            if filed is None:
                continue

            accession = accession_numbers[i]
            acc_no_dashes = _strip_accession_dashes(accession)
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            report_date_str = report_dates[i] if i < len(report_dates) else ""

            primary_doc_url = (
                f"{_SEC_WWW_BASE}/Archives/edgar/data/{cik.lstrip('0')}"
                f"/{acc_no_dashes}/{primary_doc}"
            )
            filing_index_url = (
                f"{_SEC_WWW_BASE}/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_dashes}/"
            )

            results.append(
                Filing(
                    cik=cik,
                    ticker=ticker,
                    company_name=company_name,
                    filing_type=ft,
                    accession_number=accession,
                    filed_date=filed,
                    period_of_report=_safe_date(report_date_str),
                    primary_doc_url=primary_doc_url,
                    filing_index_url=filing_index_url,
                ),
            )
            if len(results) >= limit:
                break

        return results

    # ------------------------------------------------------------------
    # Filing full text
    # ------------------------------------------------------------------

    async def get_filing_text(self, filing_url: str) -> str:
        """Download the full text of a filing document."""
        return await self._get_text(filing_url)

    # ------------------------------------------------------------------
    # XBRL company facts
    # ------------------------------------------------------------------

    async def get_company_facts(self, cik: str) -> dict[str, list[CompanyFact]]:
        """Get XBRL financial facts for a company.

        Returns a dict keyed by concept name (e.g. ``Revenues``,
        ``NetIncomeLoss``) where each value is a list of
        :class:`CompanyFact` entries sorted by end date.
        """
        padded = _pad_cik(cik)
        url = f"{_SEC_DATA_BASE}/api/xbrl/companyfacts/CIK{padded}.json"
        data = await self._get_json(url)

        result: dict[str, list[CompanyFact]] = {}
        facts_by_taxonomy: dict = data.get("facts", {})

        for _taxonomy, concepts in facts_by_taxonomy.items():
            if not isinstance(concepts, dict):
                continue
            for concept_name, concept_data in concepts.items():
                units: dict = (
                    concept_data.get("units", {}) if isinstance(concept_data, dict) else {}
                )
                for _unit, entries in units.items():
                    if not isinstance(entries, list):
                        continue
                    parsed: list[CompanyFact] = []
                    for entry in entries:
                        fact = self._parse_company_fact(entry)
                        if fact is not None:
                            parsed.append(fact)
                    if parsed:
                        parsed.sort(key=lambda f: f.end_date)
                        existing = result.get(concept_name)
                        if existing is not None:
                            existing.extend(parsed)
                            existing.sort(key=lambda f: f.end_date)
                        else:
                            result[concept_name] = parsed

        return result

    @staticmethod
    def _parse_company_fact(entry: dict) -> CompanyFact | None:
        """Parse a single XBRL fact entry, returning None on bad data."""
        try:
            end_str = entry.get("end")
            filed_str = entry.get("filed")
            if not end_str or not filed_str:
                return None
            return CompanyFact(
                value=Decimal(str(entry["val"])),
                end_date=date.fromisoformat(end_str),
                fiscal_year=int(entry.get("fy", 0)),
                fiscal_period=str(entry.get("fp", "")),
                form=str(entry.get("form", "")),
                filed_date=date.fromisoformat(filed_str),
            )
        except (KeyError, ValueError, TypeError, InvalidOperation):
            return None

    # ------------------------------------------------------------------
    # Full-text search
    # ------------------------------------------------------------------

    async def search_filings(
        self,
        query: str,
        forms: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int = 20,
    ) -> list[Filing]:
        """Full-text search across EDGAR filings."""
        params: dict[str, str] = {"q": query}
        if forms:
            params["forms"] = forms
        if start_date or end_date:
            params["dateRange"] = "custom"
            if start_date:
                params["startdt"] = start_date
            if end_date:
                params["enddt"] = end_date

        url = f"{_SEC_EFTS_BASE}/LATEST/search-index"
        await self._limiter.acquire()
        response = await self._client.get(url, params=params)
        if response.status_code != 200:
            raise EdgarError(response.status_code, f"EFTS search for '{query}'")

        data = response.json()
        hits: list[dict] = []
        hits_wrapper = data.get("hits", {})
        if isinstance(hits_wrapper, dict):
            hits = hits_wrapper.get("hits", [])

        results: list[Filing] = []
        for hit in hits:
            source = hit.get("_source", {})
            if not isinstance(source, dict):
                continue

            form = source.get("form_type", "")
            ft = _filing_type_or_none(form)
            if ft is None:
                continue

            filed = _safe_date(source.get("file_date", ""))
            if filed is None:
                continue

            file_link = source.get("file_link", "")
            entity_name = source.get("entity_name", "")
            period = source.get("period_of_report", "")
            accession = hit.get("_id", "")

            results.append(
                Filing(
                    cik="",
                    ticker="",
                    company_name=entity_name,
                    filing_type=ft,
                    accession_number=accession,
                    filed_date=filed,
                    period_of_report=_safe_date(period),
                    primary_doc_url=file_link,
                ),
            )
            if len(results) >= limit:
                break

        return results

    # ------------------------------------------------------------------
    # 13F holdings
    # ------------------------------------------------------------------

    async def get_recent_13f_accessions(self, cik: str, limit: int = 4) -> list[Filing]:
        """Get the most recent 13F-HR filings for an investor."""
        return await self.get_company_filings(
            cik,
            filing_type=FilingType.THIRTEEN_F_HR,
            limit=limit,
        )

    async def get_13f_holdings(
        self,
        cik: str,
        accession_number: str,
        report_date: date | None = None,
    ) -> list[Holding13F]:
        """Parse a 13F filing to extract holdings.

        Fetches the filing index page to locate the information table XML,
        then parses holdings from it.
        """
        padded = _pad_cik(cik)
        cik_raw = padded.lstrip("0")
        acc_no_dashes = _strip_accession_dashes(accession_number)

        # Step 1: Fetch the filing index to find the information table document.
        index_url = f"{_SEC_WWW_BASE}/Archives/edgar/data/{cik_raw}/{acc_no_dashes}/"
        index_html = await self._get_text(index_url)
        info_table_url = self._find_info_table_url(index_html, index_url)

        if info_table_url is None:
            logger.warning(
                "No information table found for CIK=%s accession=%s",
                cik,
                accession_number,
            )
            return []

        # Step 2: Fetch and parse the XML.
        xml_text = await self._get_text(info_table_url)
        return self._parse_13f_xml(
            xml_text,
            investor_id=padded,
            accession_number=accession_number,
            report_date=report_date or date.today(),
        )

    @staticmethod
    def _find_info_table_url(index_html: str, base_url: str) -> str | None:
        """Scan the filing index page HTML for the information table link.

        Looks for links whose text or href contains ``infotable`` (case-
        insensitive), which is the standard naming convention for 13F
        information table documents.
        """
        lower = index_html.lower()
        # Look for anchor tags whose href points to the info table.
        for match in re.finditer(r'href="([^"]+)"', index_html, re.IGNORECASE):
            href = match.group(1)
            if "infotable" in href.lower():
                if href.startswith("http"):
                    return href
                return base_url.rstrip("/") + "/" + href.lstrip("/")

        # Fallback: look for any XML link with "INFORMATION TABLE" nearby.
        for match in re.finditer(
            r'href="([^"]+\.xml)"[^>]*>[^<]*',
            index_html,
            re.IGNORECASE,
        ):
            href = match.group(1)
            # Check surrounding context for "information table".
            start = max(0, match.start() - 200)
            end = min(len(lower), match.end() + 200)
            context = lower[start:end]
            if "information table" in context:
                if href.startswith("http"):
                    return href
                return base_url.rstrip("/") + "/" + href.lstrip("/")

        return None

    @staticmethod
    def _parse_13f_xml(
        xml_text: str,
        investor_id: str,
        accession_number: str,
        report_date: date,
    ) -> list[Holding13F]:
        """Parse 13F information table XML into Holding13F models."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("Failed to parse 13F XML for accession %s", accession_number)
            return []

        # Detect namespace — the 13F schema namespace varies across filings.
        ns_uri = ""
        tag = root.tag
        if tag.startswith("{"):
            ns_uri = tag[1 : tag.index("}")]

        def _find(element: ET.Element, local_name: str) -> str:
            """Find a child element by local name regardless of namespace."""
            if ns_uri:
                child = element.find(f"{{{ns_uri}}}{local_name}")
            else:
                child = element.find(local_name)
            if child is None:
                # Brute-force: scan children for matching local name.
                for c in element:
                    if c.tag.rpartition("}")[-1] == local_name:
                        return (c.text or "").strip()
                return ""
            return (child.text or "").strip()

        def _find_nested(element: ET.Element, path: list[str]) -> str:
            """Walk a path of local-name segments."""
            current = element
            for segment in path:
                found = None
                if ns_uri:
                    found = current.find(f"{{{ns_uri}}}{segment}")
                if found is None:
                    for c in current:
                        if c.tag.rpartition("}")[-1] == segment:
                            found = c
                            break
                if found is None:
                    return ""
                current = found
            return (current.text or "").strip()

        # Iterate over infoTable entries.
        entries: list[ET.Element] = []
        for child in root.iter():
            local = child.tag.rpartition("}")[-1]
            if local == "infoTable":
                entries.append(child)

        holdings: list[Holding13F] = []
        for entry in entries:
            name_of_issuer = _find(entry, "nameOfIssuer")
            cusip = _find(entry, "cusip")
            value_str = _find(entry, "value")
            shares_str = _find_nested(entry, ["shrsOrPrnAmt", "sshPrnamt"])
            share_type = _find_nested(entry, ["shrsOrPrnAmt", "sshPrnamtType"])
            discretion = _find(entry, "investmentDiscretion")

            try:
                value_thousands = Decimal(value_str) if value_str else Decimal("0")
                value_usd = value_thousands * 1000
            except InvalidOperation:
                value_usd = Decimal("0")

            try:
                shares = int(Decimal(shares_str)) if shares_str else 0
            except (InvalidOperation, ValueError):
                shares = 0

            holdings.append(
                Holding13F(
                    investor_id=investor_id,
                    filing_accession=accession_number,
                    report_date=report_date,
                    ticker="",  # 13F XML doesn't include tickers, only CUSIP
                    company_name=name_of_issuer,
                    cusip=cusip,
                    value_usd=value_usd,
                    shares=shares,
                    share_type=share_type.upper() or "SH",
                    investment_discretion=discretion.upper() or "SOLE",
                ),
            )

        return holdings

    # ------------------------------------------------------------------
    # Insider trades (Form 4) — metadata only for now
    # ------------------------------------------------------------------

    async def get_insider_trades(self, cik: str, limit: int = 50) -> list[InsiderTrade]:
        """Get recent insider trade filings (Form 4) for a company.

        Full XML parsing of Form 4 transaction details is not yet
        implemented.  Returns an empty list until that work is done.
        """
        return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> EdgarProvider:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
