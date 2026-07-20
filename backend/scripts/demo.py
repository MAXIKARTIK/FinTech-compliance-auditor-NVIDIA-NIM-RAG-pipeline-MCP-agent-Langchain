"""End-to-end demo: ingest a sample filing -> poll -> run audit -> print + export PDF.

Run from the repo root (D:\\fintech) after `docker compose up` and seeding:
    python backend/scripts/demo.py                 # uses samples/10kgoogle.pdf
    python backend/scripts/demo.py path/to/file.pdf
"""

import os
import sys
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"

def _load_api_key() -> str:
    """Read API_KEY straight from the repo-root .env (no need to `set` it)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"   # D:\fintech\.env
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("API_KEY", "change-me")

HEADERS = {"X-API-Key": _load_api_key()}
TICKER, TYPE, YEAR, QUARTER = "PYPL", "10-K", 2025, "FY"
DEFAULT_PDF = "samples/10kgoogle.pdf"

def main(pdf_path: str) -> None:
    with open(pdf_path, "rb") as fh:
        r = httpx.post(
            f"{API}/filings/ingest",
            headers=HEADERS,
            data={
                "ticker": TICKER,
                "filing_type": TYPE,
                "fiscal_year": YEAR,
                "fiscal_quarter": QUARTER,
            },
            files={"file": fh},
            timeout=30,
        )
    r.raise_for_status()
    filing_id = r.json()["filing_id"]
    print(f"Ingested filing {filing_id}, waiting for indexing...")

    for _ in range(60):
        status = httpx.get(f"{API}/filings/{filing_id}").json()["status"]
        print(f"  status={status}")
        if status in ("indexed", "failed"):
            break
        time.sleep(2)

    r = httpx.post(
        f"{API}/audit/run",
        headers=HEADERS,
        json={
            "ticker": TICKER,
            "filing_type": TYPE,
            "fiscal_year": YEAR,
            "fiscal_quarter": QUARTER,
        },
        timeout=30,
    )
    r.raise_for_status()
    run_id = r.json()["audit_run_id"]
    print(f"Started audit {run_id}, waiting for completion...")

    report = {}
    for _ in range(60):
        report = httpx.get(f"{API}/audit/report/{run_id}").json()
        if report.get("status") == "completed":
            break
        time.sleep(2)

    print(f"\nCompliance score: {report.get('compliance_score')}")
    for f in report.get("findings", []):
        print(f"  [{f['severity']}] {f['rule_id']}: {f['status']} - {f['explanation']}")

    pdf = httpx.get(f"{API}/audit/report/{run_id}/pdf", timeout=60).content
    with open(f"audit_{run_id}.pdf", "wb") as fh:
        fh.write(pdf)
    print(f"\nSaved audit_{run_id}.pdf")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF)
