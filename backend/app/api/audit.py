from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth import require_api_key
from app.config import get_settings
from app.db import get_session
from app.models import AuditRun, Filing, Finding, Rule
from app.schemas import AuditRunRequest, ReportOut
from app.services.reports import render_pdf, report_json

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/run", status_code=202, dependencies=[Depends(require_api_key)])
async def run_audit(payload: AuditRunRequest, db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Filing).where(
            Filing.ticker == payload.ticker,
            Filing.filing_type == payload.filing_type,
            Filing.fiscal_year == payload.fiscal_year,
            Filing.fiscal_quarter == payload.fiscal_quarter,
        )
    )
    filing = res.scalar_one_or_none()
    if filing is None:
        raise HTTPException(status_code=404, detail="filing not found for ticker/type/period")
    if filing.status != "indexed":
        raise HTTPException(status_code=409, detail=f"filing not indexed (status={filing.status})")

    stmt = select(Rule).where(Rule.is_active.is_(True))
    if payload.rule_ids:
        stmt = stmt.where(Rule.rule_id.in_(payload.rule_ids))
    rules = (await db.execute(stmt)).scalars().all()
    if not rules:
        raise HTTPException(status_code=400, detail="no matching active rules")
    s = get_settings()
    run = AuditRun(
        filing_id=filing.id,
        status="running",
        model_name=s.chat_model,
        model_params={
            "reasoning_budget": s.reasoning_budget,
            "enable_thinking": s.enable_thinking,
            "temperature": s.chat_temperature,
            "top_p": s.chat_top_p,
            "retrieval_top_k": s.retrieval_top_k,
        },
        rule_versions={r.rule_id: r.version for r in rules},  # snapshot (R6)
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.worker import celery_app

    celery_app.send_task("run_audit", args=[run.id])
    return {"audit_run_id": run.id, "status": run.status}


async def _load_report(run_id: str, db: AsyncSession) -> dict:
    run = await db.get(AuditRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="audit run not found")
    filing = await db.get(Filing, run.filing_id)
    res = await db.execute(select(Finding).where(Finding.audit_run_id == run_id))
    return report_json(run, filing, res.scalars().all())


@router.get("/report/{run_id}", response_model=ReportOut)
async def get_report(run_id: str, db: AsyncSession = Depends(get_session)):
    return await _load_report(run_id, db)


@router.get("/report/{run_id}/pdf")
async def get_report_pdf(run_id: str, db: AsyncSession = Depends(get_session)):
    report = await _load_report(run_id, db)
    pdf = await run_in_threadpool(render_pdf, report)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="audit_{run_id}.pdf"'},
    )
