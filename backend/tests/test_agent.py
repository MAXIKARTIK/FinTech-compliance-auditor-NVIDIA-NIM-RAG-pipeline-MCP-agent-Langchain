"""MCP agent (R7): mocked tools assert fetch->audit->history->alert order and that
Critical findings trigger Slack while alert failures never fail the run."""

import asyncio

import pytest

from app.agent import graph as agent_graph


@pytest.fixture
def mocked_agent(monkeypatch):
    calls = []

    async def fake_fetch(ticker):
        calls.append("fetch")
        return {"ticker": ticker, "form": "10-K"}

    def fake_audit(ticker):
        calls.append("audit")
        return {
            "audit_run_id": "run-1",
            "ticker": ticker,
            "compliance_score": 40,
            "findings": [{"rule_id": "SOX-302", "severity": "Critical"}],
        }

    async def fake_history(ticker):
        calls.append("history")
        return [{"audit_run_id": "old", "compliance_score": 80}]

    async def fake_alert(text):
        calls.append("alert")

    monkeypatch.setattr(agent_graph.mcp_tools, "fetch_and_ingest_from_edgar", fake_fetch)
    monkeypatch.setattr(agent_graph.mcp_tools, "query_audit_history", fake_history)
    monkeypatch.setattr(agent_graph.mcp_tools, "send_slack_alert", fake_alert)
    monkeypatch.setattr(
        "app.services.audit_service.create_and_run_audit_for_latest_filing", fake_audit
    )
    return calls


def test_agent_runs_fetch_audit_history_alert_in_order(mocked_agent):
    state = asyncio.run(agent_graph.run_agent_audit("AAPL"))
    assert mocked_agent == ["fetch", "audit", "history", "alert"]
    assert state["alert_sent"] is True


def test_no_critical_means_no_alert(monkeypatch):
    async def fake_fetch(t):
        return {"ticker": t}

    def fake_audit(t):
        return {
            "audit_run_id": "r",
            "compliance_score": 100,
            "findings": [{"rule_id": "X", "severity": "Low"}],
        }

    async def fake_history(t):
        return []

    alerted = []

    async def fake_alert(text):
        alerted.append(text)

    monkeypatch.setattr(agent_graph.mcp_tools, "fetch_and_ingest_from_edgar", fake_fetch)
    monkeypatch.setattr(agent_graph.mcp_tools, "query_audit_history", fake_history)
    monkeypatch.setattr(agent_graph.mcp_tools, "send_slack_alert", fake_alert)
    monkeypatch.setattr(
        "app.services.audit_service.create_and_run_audit_for_latest_filing", fake_audit
    )
    asyncio.run(agent_graph.run_agent_audit("AAPL"))
    assert alerted == []


def test_alert_failure_does_not_fail_run(mocked_agent, monkeypatch):
    async def boom(text):
        raise RuntimeError("slack down")

    monkeypatch.setattr(agent_graph.mcp_tools, "send_slack_alert", boom)
    state = asyncio.run(agent_graph.run_agent_audit("AAPL"))
    assert state["alert_sent"] is False
    assert state["report"]["compliance_score"] == 40
