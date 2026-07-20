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

def upsert_chunks(ids, documents, metadatas, embeddings=None):
    emb = embeddings or get_embeddings()
    batch = get_settings().embed_batch_size
    vectors: list[list[float]] = []
    for i in range(0, len(documents), batch):
        vectors.extend(emb.embed_documents(documents[i : i + batch]))   # passage mode, batched
    get_collection().upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)
