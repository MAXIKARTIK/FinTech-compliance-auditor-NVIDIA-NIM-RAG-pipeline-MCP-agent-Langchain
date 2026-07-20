"""MCP tool wrappers for the agentic layer (R7): fetch (SEC EDGAR), history, slack.

- fetch / ingest use the free SEC EDGAR JSON API (mandatory descriptive User-Agent).
- audit history reads Postgres directly (read-only).
- Slack alerts go via the Slack Web API (httpx) — best-effort, never fail the audit.

DB / models / ingestion are imported lazily inside functions to avoid import cycles.
"""

import asyncio
import os

import httpx

from app.config import get_settings
from app.services.filing_scope import normalize_fiscal_quarter, normalize_ticker

async def fetch_filing_from_edgar(ticker: str) -> dict:
    """Fetch the latest 10-K/10-Q filing metadata for a ticker from SEC EDGAR."""
    s = get_settings()
    headers = {"User-Agent": s.sec_edgar_user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get("https://www.sec.gov/files/company_tickers.json")
        r.raise_for_status()
        cik = None
        for entry in r.json().values():
            if entry.get("ticker", "").upper() == ticker.upper():
                cik = int(entry["cik_str"])
                break
        if cik is None:
            raise ValueError(f"ticker {ticker} not found on EDGAR")

        r2 = await client.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        r2.raise_for_status()
        recent = r2.json()["filings"]["recent"]
        for i, form in enumerate(recent["form"]):
            if form in ("10-K", "10-Q"):
                return {
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "form": form,
                    "accession_number": recent["accessionNumber"][i],
                    "filing_date": recent["filingDate"][i],
                    "primary_document": recent["primaryDocument"][i],
                }
        raise ValueError(f"no 10-K/10-Q found for {ticker}")

async def fetch_and_ingest_from_edgar(ticker: str, *, fiscal_quarter: str = "FY") -> dict:
    """Fetch the latest filing from EDGAR, download the primary document, and ingest it.

    Runs the blocking parse+embed+upsert in a worker thread, then marks the Filing
    'indexed' so the agent can audit it immediately.
    """
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import Company, Filing
    from app.services.ingestion import ingest_pdf

    s = get_settings()
    ticker = normalize_ticker(ticker)
    fiscal_quarter = normalize_fiscal_quarter(fiscal_quarter)

    meta = await fetch_filing_from_edgar(ticker)
    acc = meta["accession_number"].replace("-", "")
    doc_url = (
        f"https://www.sec.gov/Archives/edgar/data/{meta['cik']}/{acc}/{meta['primary_document']}"
    )
    fiscal_year = int(meta["filing_date"][:4])

    async with httpx.AsyncClient(
        headers={"User-Agent": s.sec_edgar_user_agent}, timeout=90, follow_redirects=True
    ) as client:
        r = await client.get(doc_url)
        r.raise_for_status()
        content = r.content

    ext = ".pdf" if meta["primary_document"].lower().endswith(".pdf") else ".html"
    os.makedirs(s.upload_dir, exist_ok=True)
    path = os.path.join(
        s.upload_dir, f"{ticker}_{meta['form']}_{fiscal_year}_{fiscal_quarter}{ext}"
    )
    with open(path, "wb") as fh:
        fh.write(content)

    async with get_sessionmaker()() as db:
        if not await db.get(Company, ticker):
            db.add(Company(ticker=ticker, name=ticker))
        res = await db.execute(
            select(Filing).where(
                Filing.ticker == ticker,
                Filing.filing_type == meta["form"],
                Filing.fiscal_year == fiscal_year,
                Filing.fiscal_quarter == fiscal_quarter,
            )
        )
        filing = res.scalar_one_or_none()
        if filing is None:
            filing = Filing(
                ticker=ticker,
                filing_type=meta["form"],
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
            )
            db.add(filing)
        filing.file_path = path
        filing.status = "processing"
        await db.commit()
        await db.refresh(filing)
        filing_id = filing.id

    count = await asyncio.to_thread(
        ingest_pdf,
        path,
        ticker=ticker,
        filing_type=meta["form"],
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
    )

    async with get_sessionmaker()() as db:
        filing = await db.get(Filing, filing_id)
        filing.status = "indexed" if count else "failed"
        await db.commit()

    meta.update(
        {"doc_url": doc_url, "fiscal_year": fiscal_year, "fiscal_quarter": fiscal_quarter}
    )
    return meta

async def query_audit_history(ticker: str) -> list[dict]:
    """Read past audit runs for a ticker (read-only)."""
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import AuditRun, Filing

    async with get_sessionmaker()() as db:
        res = await db.execute(
            select(AuditRun, Filing)
            .join(Filing, AuditRun.filing_id == Filing.id)
            .where(Filing.ticker == ticker.upper())
            .order_by(AuditRun.created_at.desc())
        )
        return [
            {
                "audit_run_id": run.id,
                "compliance_score": run.compliance_score,
                "status": run.status,
                "created_at": str(run.created_at),
            }
            for run, _filing in res.all()
        ]

async def send_slack_alert(text: str) -> None:
    """Post a Critical-finding alert to Slack via the Web API (best-effort)."""
    s = get_settings()
    if not s.slack_mcp_token:
        raise RuntimeError("slack token not configured")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {s.slack_mcp_token}"},
            json={"channel": s.slack_channel, "text": text},
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"slack error: {data.get('error')}")

def send_slack_alert_sync(text: str) -> None:
    asyncio.run(send_slack_alert(text))
