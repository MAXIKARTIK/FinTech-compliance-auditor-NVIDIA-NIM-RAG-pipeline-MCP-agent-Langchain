import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")


class Filing(Base):
    """One corporate filing per (ticker, type, fiscal period). Re-ingest is idempotent (R1)."""

    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "filing_type", "fiscal_year", "fiscal_quarter", name="uq_filing_period"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(ForeignKey("companies.ticker"), index=True)
    filing_type: Mapped[str] = mapped_column(String(10))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_quarter: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Rule(Base):
    """Versioned compliance rule (R3). Updates create a new version; history is immutable."""

    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_rule_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(50), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    title: Mapped[str] = mapped_column(String(255))
    regulation: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    check_prompt: Mapped[str] = mapped_column(Text)
    severity_weight: Mapped[int] = mapped_column(Integer, default=5)


class AuditRun(Base):
    """A single audit execution; snapshots rule versions + model for reproducibility (R6)."""

    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filing_id: Mapped[str] = mapped_column(ForeignKey("filings.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="running")
    compliance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(50), default="")
    model_params: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_versions: Mapped[dict] = mapped_column(JSON, default=dict)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    audit_run_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))  # pass | fail | needs_review
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10))  # Critical | High | Medium | Low
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
