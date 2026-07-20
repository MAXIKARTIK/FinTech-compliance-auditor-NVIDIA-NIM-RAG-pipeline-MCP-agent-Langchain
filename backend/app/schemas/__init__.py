from pydantic import BaseModel, Field, field_validator

from app.services.filing_scope import (
    normalize_filing_type,
    normalize_fiscal_quarter,
    normalize_ticker,
    validate_fiscal_year,
)


# --- Rules (R3) ---
class RuleBase(BaseModel):
    title: str
    regulation: str
    description: str = ""
    check_prompt: str
    severity_weight: int = Field(ge=1, le=10)

class IngestUrlRequest(BaseModel):
    ticker: str
    filing_type: str = "10-K"
    fiscal_year: int
    fiscal_quarter: str = "FY"
    url: str

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("filing_type")
    @classmethod
    def _normalize_filing_type(cls, value: str) -> str:
        return normalize_filing_type(value)

    @field_validator("fiscal_quarter")
    @classmethod
    def _normalize_fiscal_quarter(cls, value: str) -> str:
        return normalize_fiscal_quarter(value)

    @field_validator("fiscal_year")
    @classmethod
    def _validate_fiscal_year(cls, value: int) -> int:
        return validate_fiscal_year(value)

class RuleCreate(RuleBase):
    rule_id: str


class RuleUpdate(RuleBase):
    pass


class RuleOut(RuleCreate):
    version: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- Filings (R1) ---
class FilingOut(BaseModel):
    id: str
    ticker: str
    filing_type: str
    fiscal_year: int
    fiscal_quarter: str
    status: str

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    filing_id: str
    status: str = "processing"


# --- Search (R2 debug) ---
class SearchRequest(BaseModel):
    ticker: str
    filing_type: str
    fiscal_year: int
    fiscal_quarter: str
    query: str
    k: int = Field(default=5, ge=1, le=20)

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("filing_type")
    @classmethod
    def _normalize_filing_type(cls, value: str) -> str:
        return normalize_filing_type(value)

    @field_validator("fiscal_quarter")
    @classmethod
    def _normalize_fiscal_quarter(cls, value: str) -> str:
        return normalize_fiscal_quarter(value)

    @field_validator("fiscal_year")
    @classmethod
    def _validate_fiscal_year(cls, value: int) -> int:
        return validate_fiscal_year(value)


# --- Audit (R4/R5/R6) ---
class AuditRunRequest(BaseModel):
    ticker: str
    filing_type: str
    fiscal_year: int
    fiscal_quarter: str
    rule_ids: list[str] | None = None

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("filing_type")
    @classmethod
    def _normalize_filing_type(cls, value: str) -> str:
        return normalize_filing_type(value)

    @field_validator("fiscal_quarter")
    @classmethod
    def _normalize_fiscal_quarter(cls, value: str) -> str:
        return normalize_fiscal_quarter(value)

    @field_validator("fiscal_year")
    @classmethod
    def _validate_fiscal_year(cls, value: int) -> int:
        return validate_fiscal_year(value)


class FindingOut(BaseModel):
    rule_id: str
    status: str
    severity: str
    confidence: float
    explanation: str
    evidence: list[dict]

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    audit_run_id: str
    filing_id: str
    ticker: str
    filing_type: str
    fiscal_year: int
    fiscal_quarter: str
    status: str
    compliance_score: int | None
    model_name: str
    rule_versions: dict
    findings: list[FindingOut]


# --- Agent (R7) ---
class AgentAuditRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return normalize_ticker(value)
