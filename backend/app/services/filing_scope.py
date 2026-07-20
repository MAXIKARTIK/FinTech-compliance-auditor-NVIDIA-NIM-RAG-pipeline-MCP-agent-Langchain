"""Normalization and validation helpers for filing identity fields."""

ALLOWED_FILING_TYPES = {"10-K", "10-Q"}
ALLOWED_FISCAL_QUARTERS = {"FY", "Q1", "Q2", "Q3", "Q4"}


def normalize_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    if not value:
        raise ValueError("ticker is required")
    return value


def normalize_filing_type(filing_type: str) -> str:
    value = filing_type.strip().upper()
    if value not in ALLOWED_FILING_TYPES:
        raise ValueError("filing_type must be one of: 10-K, 10-Q")
    return value


def normalize_fiscal_quarter(fiscal_quarter: str) -> str:
    value = fiscal_quarter.strip().upper()
    if value not in ALLOWED_FISCAL_QUARTERS:
        raise ValueError("fiscal_quarter must be one of: FY, Q1, Q2, Q3, Q4")
    return value


def validate_fiscal_year(fiscal_year: int) -> int:
    if fiscal_year < 1900 or fiscal_year > 2100:
        raise ValueError("fiscal_year must be between 1900 and 2100")
    return fiscal_year
