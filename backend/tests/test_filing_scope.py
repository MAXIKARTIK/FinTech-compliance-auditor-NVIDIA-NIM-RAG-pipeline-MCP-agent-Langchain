import pytest
from pydantic import ValidationError

from app.schemas import AuditRunRequest, IngestUrlRequest, SearchRequest


def test_ingest_url_normalizes_filing_identity_fields():
    payload = IngestUrlRequest(
        ticker=" pypl ",
        filing_type="10-q",
        fiscal_year=2025,
        fiscal_quarter="q4",
        url="https://example.com/filing.html",
    )
    assert payload.ticker == "PYPL"
    assert payload.filing_type == "10-Q"
    assert payload.fiscal_quarter == "Q4"


def test_audit_run_requires_filing_type():
    with pytest.raises(ValidationError):
        AuditRunRequest(ticker="PYPL", fiscal_year=2025, fiscal_quarter="FY")


def test_search_request_rejects_invalid_quarter():
    with pytest.raises(ValidationError):
        SearchRequest(
            ticker="PYPL",
            filing_type="10-K",
            fiscal_year=2025,
            fiscal_quarter="Q5",
            query="aml policy",
        )
