"""Celery worker: async PDF ingestion and audit execution (R1/R4)."""

import structlog
from celery import Celery

from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

celery_app = Celery("compliance", broker=settings.redis_url, backend=settings.redis_url)

@celery_app.task(name="ingest_filing")
def ingest_filing_task(filing_id: str) -> int:
    from app.models import Filing
    from app.services.audit_service import get_sync_sessionmaker
    from app.services.ingestion import build_chunks, extract_text
    from app.services.vectorstore import upsert_chunks

    n = 0
    with get_sync_sessionmaker()() as db:
        filing = db.get(Filing, filing_id)
        if filing is None:
            log.error("filing_not_found", filing_id=filing_id)
            return 0
        try:
            # 1) actually parse first
            text = extract_text(filing.file_path)
            if not text.strip():
                raise ValueError("no extractable text in document")
            filing.status = "parsed"          # only now is it truly parsed
            db.commit()

            # 2) chunk + embed + store
            ids, docs, metas = build_chunks(
                text,
                ticker=filing.ticker,
                filing_type=filing.filing_type,
                fiscal_year=filing.fiscal_year,
                fiscal_quarter=filing.fiscal_quarter,
            )
            if ids:
                upsert_chunks(ids, docs, metas)
            n = len(ids)
            filing.status = "indexed" if n else "failed"
            log.info("filing_indexed", filing_id=filing_id, chunks=n)
        except Exception as exc:
            filing.status = "failed"
            log.error("filing_ingest_failed", filing_id=filing_id, error=str(exc))
        db.commit()
    return n


@celery_app.task(name="run_audit")
def run_audit_task(audit_run_id: str) -> int | None:
    from app.services.alerts import maybe_alert_critical
    from app.services.audit_service import run_audit_sync

    report = run_audit_sync(audit_run_id)
    maybe_alert_critical(report)  # best-effort, never raises
    return report.get("compliance_score")
