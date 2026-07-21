import os

# Hermetic test config: force the values that determine test correctness so the
# suite can't be broken by an ambient environment (e.g. a developer who has
# exported the real .env for docker compose). These MUST override, not
# setdefault -- otherwise a shell-exported API_KEY/DATABASE_URL leaks in and
# causes spurious 401s / points the app at Postgres instead of in-memory SQLite.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["API_KEY"] = "test-key"
os.environ.setdefault("NVIDIA_API_KEY", "test-nvidia-key")   # any placeholder; LLM calls are mocked
os.environ.setdefault("LLM_PROVIDER", "nvidia")

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

TEST_API_KEY = "test-key"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


@pytest.fixture
def client(async_session):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    async def _override():
        yield async_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": TEST_API_KEY}
