"""LangGraph MCP agent (R7): fetch -> audit -> history -> (Critical? -> alert).

Side effects (Slack alerts) are triggered by graph logic, never directly by LLM
output. Alerting is best-effort and never fails the run.
"""

import asyncio
from typing import TypedDict

import structlog
from langgraph.graph import END, StateGraph

from app.agent import mcp_tools

log = structlog.get_logger()


class AgentState(TypedDict, total=False):
    ticker: str
    filing: dict
    report: dict
    history: list
    alert_sent: bool


async def node_fetch(state: AgentState) -> AgentState:
    state["filing"] = await mcp_tools.fetch_and_ingest_from_edgar(state["ticker"])
    return state


async def node_audit(state: AgentState) -> AgentState:
    from app.services import audit_service

    state["report"] = await asyncio.to_thread(
        audit_service.create_and_run_audit_for_latest_filing, state["ticker"]
    )
    return state


async def node_history(state: AgentState) -> AgentState:
    state["history"] = await mcp_tools.query_audit_history(state["ticker"])
    return state


async def node_alert(state: AgentState) -> AgentState:
    report = state.get("report") or {}
    criticals = [f for f in report.get("findings", []) if f.get("severity") == "Critical"]
    rules = ", ".join(f["rule_id"] for f in criticals)
    text = (
        f":rotating_light: CRITICAL findings for {state['ticker']}: {rules}. "
        f"Score: {report.get('compliance_score')}. "
        f"Report: /audit/report/{report.get('audit_run_id')}"
    )
    try:
        await mcp_tools.send_slack_alert(text)
        state["alert_sent"] = True
    except Exception as exc:  # best-effort (R7)
        log.warning("slack_alert_failed", error=str(exc))
        state["alert_sent"] = False
    return state


def _route_after_history(state: AgentState) -> str:
    report = state.get("report") or {}
    if any(f.get("severity") == "Critical" for f in report.get("findings", [])):
        return "alert"
    return "end"


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("fetch", node_fetch)
    g.add_node("audit", node_audit)
    g.add_node("history", node_history)
    g.add_node("alert", node_alert)
    g.set_entry_point("fetch")
    g.add_edge("fetch", "audit")
    g.add_edge("audit", "history")
    g.add_conditional_edges("history", _route_after_history, {"alert": "alert", "end": END})
    g.add_edge("alert", END)
    return g


async def run_agent_audit(ticker: str) -> dict:
    graph = build_graph().compile()
    return await graph.ainvoke({"ticker": ticker.upper()})
