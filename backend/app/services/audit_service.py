"""Audit orchestration shared by the Celery worker and the MCP agent (R4/R5/R6)."""

import hashlib
import os

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


def _file_hash(path: str) -> str:
    """SHA-256 of the raw filing bytes, or "" if unreadable. Used as a cache key so
    re-ingesting different content under the same filing invalidates finding reuse."""
    if not path or not os.path.exists(path):
        return ""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return ""


def _cached_finding(db, run, rule):
    """Return a prior Finding evaluated under identical conditions, if one exists.

    Match = same filing, same model + model_params (which now includes the content
    hash), same rule version, from an earlier completed run. This makes an identical
    re-run reuse the previous verdict instead of re-invoking the LLM.
    """
    target_params = run.model_params or {}
    candidates = (
        db.execute(
            select(AuditRun)
            .where(
                AuditRun.filing_id == run.filing_id,
                AuditRun.id != run.id,
                AuditRun.status == "completed",
                AuditRun.model_name == run.model_name,
            )
            .order_by(AuditRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    for cand in candidates:
        if (cand.model_params or {}) != target_params:
            continue
        if (cand.rule_versions or {}).get(rule.rule_id) != rule.version:
            continue
        found = (
            db.execute(
                select(Finding).where(
                    Finding.audit_run_id == cand.id, Finding.rule_id == rule.rule_id
                )
            )
            .scalars()
            .first()
        )
        if found is not None:
            return found
    return None


def run_audit_sync(audit_run_id: str, session_factory=None) -> dict:
    """Evaluate every snapshotted rule version, persist findings + score, return report."""
    settings = get_settings()
    factory = session_factory or get_sync_sessionmaker()
    with factory() as db:
        run = db.get(AuditRun, audit_run_id)
        if run is None:
            raise ValueError(f"audit run {audit_run_id} not found")
        filing = db.get(Filing, run.filing_id)
        if filing is None:
            raise ValueError(f"filing {run.filing_id} not found for audit run {audit_run_id}")
        # Fingerprint the exact bytes being audited and fold it into model_params so
        # cached findings are only reused when the filing content is unchanged.
        content_hash = _file_hash(filing.file_path) if settings.audit_reuse_findings else ""
        run.model_params = {**(run.model_params or {}), "content_hash": content_hash}
        rule_versions: dict = run.rule_versions or {}
        rows = (
            db.execute(select(Rule).where(Rule.rule_id.in_(list(rule_versions.keys()))))
            .scalars()
            .all()
        )
        rules = [r for r in rows if rule_versions.get(r.rule_id) == r.version]

        results: list[tuple[str, int]] = []
        for rule in rules:
            cached = (
                _cached_finding(db, run, rule)
                if settings.audit_reuse_findings and content_hash
                else None
            )
            if cached is not None:
                db.add(
                    Finding(
                        audit_run_id=run.id,
                        rule_id=rule.rule_id,
                        status=cached.status,
                        severity=cached.severity,
                        confidence=cached.confidence,
                        explanation=cached.explanation,
                        evidence=cached.evidence or [],
                        reasoning=cached.reasoning or "",
                    )
                )
                results.append((cached.status, rule.severity_weight))
                continue
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
