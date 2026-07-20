from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


async def _check_postgres(settings: Settings) -> str:
    try:
        from sqlalchemy import text

        from app.db import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # pragma: no cover - env dependent
        return f"error: {type(exc).__name__}"


async def _check_redis(settings: Settings) -> str:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        return "ok"
    except Exception as exc:  # pragma: no cover - env dependent
        return f"error: {type(exc).__name__}"


async def _check_chroma(settings: Settings) -> str:
    try:
        from app.services.vectorstore import get_chroma_client

        get_chroma_client().heartbeat()
        return "ok"
    except Exception as exc:  # pragma: no cover - env dependent
        return f"error: {type(exc).__name__}"


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "api": "ok",
        "postgres": await _check_postgres(settings),
        "redis": await _check_redis(settings),
        "chroma": await _check_chroma(settings),
    }
