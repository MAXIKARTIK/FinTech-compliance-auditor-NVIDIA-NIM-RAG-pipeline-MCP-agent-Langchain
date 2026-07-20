"""Pure risk-scoring functions (R5). No I/O; fully unit-testable."""

CRITICAL = "Critical"
HIGH = "High"
MEDIUM = "Medium"
LOW = "Low"


def severity_for(status: str, weight: int) -> str:
    """Severity for a finding. Only failures escalate by weight; reviews are Medium."""
    if status == "fail":
        if weight >= 8:
            return CRITICAL
        if weight >= 5:
            return HIGH
        if weight >= 3:
            return MEDIUM
        return LOW
    if status == "needs_review":
        return MEDIUM
    return LOW


def compliance_score(results: list[tuple[str, int]]) -> int:
    """100 - (failed_weights / total_weights * 100), clamped to [0, 100].

    `results` is a list of (status, severity_weight) tuples.
    """
    total = sum(w for _, w in results)
    if total <= 0:
        return 100
    failed = sum(w for s, w in results if s == "fail")
    return max(0, min(100, round(100 - failed / total * 100)))
