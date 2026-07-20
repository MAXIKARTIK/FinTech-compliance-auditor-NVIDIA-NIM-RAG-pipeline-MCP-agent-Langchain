from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.schemas import AgentAuditRequest

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/audit", dependencies=[Depends(require_api_key)])
async def agent_audit(payload: AgentAuditRequest) -> dict:
    """MCP-driven autonomous audit (R7): fetch from EDGAR -> audit -> history -> alert."""
    from app.agent.graph import run_agent_audit

    try:
        state = await run_agent_audit(payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "ticker": payload.ticker.upper(),
        "filing": state.get("filing"),
        "report": state.get("report"),
        "history": state.get("history", []),
        "alert_sent": state.get("alert_sent", False),
    }
