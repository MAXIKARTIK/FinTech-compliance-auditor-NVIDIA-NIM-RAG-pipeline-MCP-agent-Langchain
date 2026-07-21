"""ChromaDB access layer (R2). One shared collection; isolation via metadata filters."""

import chromadb

from app.config import get_settings
from app.services.embeddings import get_embeddings
_client = None

COLLECTION_NAME = "filings"


def get_chroma_client():
    global _client
    if _client is None:
        s = get_settings()
        _client = chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port)
    return _client


def get_collection():
    return get_chroma_client().get_or_create_collection(COLLECTION_NAME)

def _scope_where(meta: dict) -> dict:
    """Metadata filter selecting every chunk belonging to one filing (ticker+period)."""
    keys = ("ticker", "filing_type", "fiscal_year", "fiscal_quarter")
    return {"$and": [{k: {"$eq": meta[k]}} for k in keys if k in meta]}


def upsert_chunks(ids, documents, metadatas, embeddings=None):
    if not ids:
        return
    emb = embeddings or get_embeddings()
    batch = get_settings().embed_batch_size
    vectors: list[list[float]] = []
    for i in range(0, len(documents), batch):
        vectors.extend(emb.embed_documents(documents[i : i + batch]))   # passage mode, batched
    col = get_collection()
    # Idempotent re-ingest (R1): drop any prior vectors for this filing scope first,
    # so a shorter re-parse can't leave orphaned higher-index chunks behind.
    if metadatas:
        try:
            col.delete(where=_scope_where(metadatas[0]))
        except Exception:
            pass
    col.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)
