from functools import lru_cache
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from app.config import get_settings

@lru_cache
def get_embeddings():
    s = get_settings()
    return NVIDIAEmbeddings(model=s.embedding_model, api_key=s.nvidia_api_key, truncate="END")
