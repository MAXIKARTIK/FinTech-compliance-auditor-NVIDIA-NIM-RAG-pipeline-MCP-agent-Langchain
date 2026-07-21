from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.schemas import SearchRequest
from app.services.retriever import retrieve

router = APIRouter(tags=["search"])


@router.post("/search", dependencies=[Depends(require_api_key)])
async def search(payload: SearchRequest) -> dict:
    """Debug endpoint (R2): metadata-isolated semantic search."""
    chunks = retrieve(
        ticker=payload.ticker,
        filing_type=payload.filing_type,
        fiscal_year=payload.fiscal_year,
        fiscal_quarter=payload.fiscal_quarter,
        query=payload.query,
        k=payload.k,
    )
    return {"count": len(chunks), "chunks": chunks}
