import os

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.config import get_settings
from app.db import get_session
from app.models import Company, Filing
from app.schemas import FilingOut, IngestResponse, IngestUrlRequest
from app.services.filing_scope import (
    normalize_filing_type,
    normalize_fiscal_quarter,
    normalize_ticker,
    validate_fiscal_year,
)

router = APIRouter(prefix="/filings", tags=["filings"])

@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
async def ingest_filing(
    ticker: str = Form(...),
    filing_type: str = Form(...),
    fiscal_year: int = Form(...),
    fiscal_quarter: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    """Accept a filing PDF, persist it, and enqueue async parsing (R1).

    Idempotent: re-uploading the same (ticker, type, period) reuses the Filing row
    and re-indexes with deterministic chunk ids (no duplicate vectors).
    """
    try:
        ticker = normalize_ticker(ticker)
        filing_type = normalize_filing_type(filing_type)
        fiscal_year = validate_fiscal_year(fiscal_year)
        fiscal_quarter = normalize_fiscal_quarter(fiscal_quarter)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not await db.get(Company, ticker):
        db.add(Company(ticker=ticker, name=ticker))

    res = await db.execute(
        select(Filing).where(
            Filing.ticker == ticker,
            Filing.filing_type == filing_type,
            Filing.fiscal_year == fiscal_year,
            Filing.fiscal_quarter == fiscal_quarter,
        )
    )
    filing = res.scalar_one_or_none()
    if filing is None:
        filing = Filing(
            ticker=ticker,
            filing_type=filing_type,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
        )
        db.add(filing)
    filing.status = "processing"

    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(
        settings.upload_dir, f"{ticker}_{filing_type}_{fiscal_year}_{fiscal_quarter}.pdf"
    )
    with open(path, "wb") as fh:
        fh.write(await file.read())
    filing.file_path = path

    await db.commit()
    await db.refresh(filing)

    from app.worker import celery_app  # lazy: keep API import light

    celery_app.send_task("ingest_filing", args=[filing.id])
    return IngestResponse(filing_id=filing.id)

@router.post(
    "/ingest-url",
    response_model=IngestResponse,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
async def ingest_filing_url(
    payload: IngestUrlRequest,
    db: AsyncSession = Depends(get_session),
):
    """Download a report from a URL (PDF or HTML) and enqueue async parsing (R1).

    Works for SEC EDGAR .htm documents and direct PDF report links. Idempotent on
    (ticker, type, period), same as the file upload path.
    """
    settings = get_settings()
    ticker = payload.ticker

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.sec_edgar_user_agent},
        timeout=60,
        follow_redirects=True,
    ) as client:
        resp = await client.get(payload.url)
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("content-type", "")

    ext = (
        ".pdf"
        if ("pdf" in content_type.lower() or payload.url.lower().endswith(".pdf"))
        else ".html"
    )

    if not await db.get(Company, ticker):
        db.add(Company(ticker=ticker, name=ticker))

    res = await db.execute(
        select(Filing).where(
            Filing.ticker == ticker,
            Filing.filing_type == payload.filing_type,
            Filing.fiscal_year == payload.fiscal_year,
            Filing.fiscal_quarter == payload.fiscal_quarter,
        )
    )
    filing = res.scalar_one_or_none()
    if filing is None:
        filing = Filing(
            ticker=ticker,
            filing_type=payload.filing_type,
            fiscal_year=payload.fiscal_year,
            fiscal_quarter=payload.fiscal_quarter,
        )
        db.add(filing)
    filing.status = "processing"

    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(
        settings.upload_dir,
        f"{ticker}_{payload.filing_type}_{payload.fiscal_year}_{payload.fiscal_quarter}{ext}",
    )
    with open(path, "wb") as fh:
        fh.write(content)
    filing.file_path = path

    await db.commit()
    await db.refresh(filing)

    from app.worker import celery_app  # lazy: keep API import light

    celery_app.send_task("ingest_filing", args=[filing.id])
    return IngestResponse(filing_id=filing.id)

@router.get("", response_model=list[FilingOut])
async def list_filings(db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(Filing).order_by(Filing.created_at.desc()))
    return res.scalars().all()

@router.get("/{filing_id}", response_model=FilingOut)
async def get_filing(filing_id: str, db: AsyncSession = Depends(get_session)):
    filing = await db.get(Filing, filing_id)
    if filing is None:
        raise HTTPException(status_code=404, detail="filing not found")
    return filing
