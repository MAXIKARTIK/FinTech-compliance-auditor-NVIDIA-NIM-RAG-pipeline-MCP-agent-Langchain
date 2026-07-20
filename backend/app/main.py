import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(
        title="FinTech Corporate Compliance Auditor",
        version="0.1.0",
        description="Ingest filings, audit against compliance rules via RAG, score risk, alert.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    from app.api import health, rules, filings, search, audit, agent
    for mod in (health, rules, filings, search, audit, agent):
        app.include_router(mod.router)

    return app          # <-- this was missing

app = create_app()
