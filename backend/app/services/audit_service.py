"""Audit orchestration shared by the Celery worker and the MCP agent (R4/R5/R6)."""

import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import AuditRun, Filing, Finding, Rule
from app.services.rag_engine import evaluate_rule
from app.services.reports import report_json
from app.services.retriever import retrieve
from app.services.scoring import compliance_score, severity_for

log = structlog.get_logger()

_sync_sessionmaker = None


def get_sync_sessionmaker():
    global _sync_sessionmaker
    if _sync_sessionmaker is None:
        engine = create_engine(get_settings().sync_database_url, pool_pre_ping=True)
        _sync_sessionmaker = sessionmaker(engine)
    return _sync_sessionmaker


def run_audit_sync(audit_run_id: str, session_factory=None) -> dict:
    """Evaluate every snapshotted rule version, persist findings + score, return report."""
    settings = get_settings()
    factory = session_factory or get_sync_sessionmaker()
    with factory() as db:
        run = db.get(AuditRun, audit_run_id)
        if run is None:
            raise ValueError(f"audit run {audit_run_id} not found")
        filing = db.get(Filing, run.filing_id)
        rule_versions: dict = run.rule_versions or {}
        rows = (
            db.execute(select(Rule).where(Rule.rule_id.in_(list(rule_versions.keys()))))
            .scalars()
            .all()
        )
        rules = [r for r in rows if rule_versions.get(r.rule_id) == r.version]

        results: list[tuple[str, int]] = []
        for rule in rules:
            chunks = retrieve(
                ticker=filing.ticker,
                filing_type=filing.filing_type,
                fiscal_year=filing.fiscal_year,
                fiscal_quarter=filing.fiscal_quarter,
                query=rule.check_prompt,
                k=settings.retrieval_top_k,
            )
            finding = evaluate_rule(
                rule_id=rule.rule_id,
                title=rule.title,
                regulation=rule.regulation,
                check_prompt=rule.check_prompt,
                chunks=chunks,
            )
            severity = severity_for(finding.status, rule.severity_weight)
            db.add(
                Finding(
                    audit_run_id=run.id,
                    rule_id=rule.rule_id,
                    status=finding.status,
                    severity=severity,
                    confidence=finding.confidence,
                    explanation=finding.explanation,
                    evidence=[e.model_dump() for e in finding.evidence],
                    reasoning=finding.reasoning,
                )
            )
            results.append((finding.status, rule.severity_weight))

        run.compliance_score = compliance_score(results)
        run.status = "completed"
        db.commit()

        findings = (
            db.execute(select(Finding).where(Finding.audit_run_id == run.id)).scalars().all()
        )
        return report_json(run, filing, findings)


def create_and_run_audit_for_latest_filing(ticker: str, session_factory=None) -> dict:
    """Used by the MCP agent: audit the latest indexed filing with all active rules."""
    factory = session_factory or get_sync_sessionmaker()
    with factory() as db:
        filing = (
            db.execute(
                select(Filing)
                .where(Filing.ticker == ticker.upper(), Filing.status == "indexed")
                .order_by(Filing.created_at.desc())
            )
            .scalars()
            .first()
        )
        if filing is None:
            raise ValueError(f"no indexed filing for {ticker}")
        rules = db.execute(select(Rule).where(Rule.is_active.is_(True))).scalars().all()
        if not rules:
            raise ValueError("no active compliance rules")

        s = get_settings()
        run = AuditRun(
            filing_id=filing.id,
            status="running",
            model_name=s.chat_model,  # was s.llm_provider
            model_params={
                "reasoning_budget": s.reasoning_budget,
                "enable_thinking": s.enable_thinking,
                "temperature": s.chat_temperature,
                "top_p": s.chat_top_p,
                "retrieval_top_k": s.retrieval_top_k,
            },
            rule_versions={r.rule_id: r.version for r in rules},
        )
        db.add(run)
        db.commit()
        run_id = run.id
    return run_audit_sync(run_id, session_factory=factory)
