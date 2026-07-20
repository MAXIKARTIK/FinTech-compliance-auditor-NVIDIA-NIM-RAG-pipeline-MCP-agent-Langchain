from functools import lru_cache

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    database_url: str = "postgresql+asyncpg://compliance:compliance@localhost:5432/compliance"
    sync_database_url: str = "postgresql+psycopg2://compliance:compliance@localhost:5432/compliance"
    redis_url: str = "redis://localhost:6379/0"
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # --- LLM (NVIDIA NIM) ---
    llm_provider: str = "nvidia"
    nvidia_api_key: str = ""
    chat_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    reasoning_budget: int = 16384
    enable_thinking: bool = True
    chat_temperature: float = 1.0        # used by get_llm
    chat_top_p: float = 0.95             # used by get_llm

    # --- Embeddings (NVIDIA NIM) ---
    embedding_model: str = "nvidia/nemotron-3-embed-1b"   # FIX: was nemotron-3-embed-8b (not hosted)
    embed_dim: int = 2048
    embed_batch_size: int = 64           # used by vectorstore.upsert_chunks  <-- the current crash

    # --- Retrieval ---
    retrieval_top_k: int = 8             # used by audit_service

    # --- Auth ---
    api_key: str = "change-me"

    # --- MCP / integrations ---
    slack_mcp_token: str = ""
    slack_channel: str = "#compliance-alerts"
    sec_edgar_user_agent: str = "FinSci Compliance Auditor admin@example.com"

    # --- Misc ---
    log_level: str = "INFO"
    upload_dir: str = "/data/uploads"

    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
