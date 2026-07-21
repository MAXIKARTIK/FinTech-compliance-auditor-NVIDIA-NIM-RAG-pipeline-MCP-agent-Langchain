"""Metadata-first isolated retrieval (R2).

The ChromaDB `where` filter on ticker + fiscal period is applied BEFORE vector
similarity, guaranteeing zero cross-tenant contamination.
"""

from app.services.vectorstore import get_collection
from app.services.embeddings import get_embeddings

def build_where(ticker: str, filing_type: str, fiscal_year: int, fiscal_quarter: str) -> dict:
    return {
        "$and": [
            {"ticker": {"$eq": ticker}},
            {"filing_type": {"$eq": filing_type}},
            {"fiscal_year": {"$eq": fiscal_year}},
            {"fiscal_quarter": {"$eq": fiscal_quarter}},
        ]
    }

def _order_key(chunk_id: str):
    """Sort key: document order by trailing chunk index, stable for any id shape."""
    tail = chunk_id.rsplit("-", 1)[-1]
    return (0, int(tail)) if tail.isdigit() else (1, chunk_id)


def retrieve(
    *, ticker, filing_type, fiscal_year, fiscal_quarter, query, k=5, collection=None, embeddings=None
):
    col = collection if collection is not None else get_collection()
    emb = embeddings or get_embeddings()
    query_embedding = emb.embed_query(query)                # query mode
    res = col.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=build_where(ticker, filing_type, fiscal_year, fiscal_quarter),
    )
    ids = res.get("ids") or [[]]
    docs = res.get("documents") or [[]]
    # Deterministic prompt order regardless of Chroma's similarity-hit ordering,
    # so the same chunk set always yields the same prompt (and same verdict).
    pairs = sorted(zip(ids[0], docs[0]), key=lambda p: _order_key(p[0]))
    return [{"chunk_id": i, "text": d} for i, d in pairs]
