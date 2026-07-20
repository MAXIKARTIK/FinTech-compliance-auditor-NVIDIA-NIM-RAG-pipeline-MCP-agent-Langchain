"""Best-effort Critical alerting (R7). Failures are logged, never fail the audit."""

import structlog

log = structlog.get_logger()


def maybe_alert_critical(report: dict) -> bool:
    criticals = [f for f in report.get("findings", []) if f.get("severity") == "Critical"]
    if not criticals:
        return False
    rules = ", ".join(f["rule_id"] for f in criticals)
    text = (
        f":rotating_light: CRITICAL compliance findings for {report.get('ticker')} "
        f"{report.get('fiscal_quarter')} FY{report.get('fiscal_year')} - rules: {rules}. "
        f"Score: {report.get('compliance_score')}. Report: /audit/report/{report.get('audit_run_id')}"
    )
    try:
        from app.agent.mcp_tools import send_slack_alert_sync

        send_slack_alert_sync(text)
        return True
    except Exception as exc:
        log.warning("slack_alert_failed", error=str(exc))
        return False
