"""RAG engine (R4): mocked LLM -> structured finding; malformed output -> needs_review."""

from app.services.rag_engine import RuleFinding, evaluate_rule
from app.services.scoring import compliance_score, severity_for


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _prompt):
        return FakeMsg(self._content)


def test_structured_finding_parses_and_passes_evidence():
    llm = FakeLLM(
        '{"status": "fail", "evidence": [{"chunk_id": "c1", "quote": "no cert"}], '
        '"explanation": "Missing certification", "confidence": 0.9}'
    )
    finding = evaluate_rule(
        rule_id="SOX-302",
        title="Cert",
        regulation="SOX",
        check_prompt="certified?",
        chunks=[{"chunk_id": "c1", "text": "..."}],
        llm=llm,
    )
    assert isinstance(finding, RuleFinding)
    assert finding.status == "fail"
    assert finding.evidence[0].chunk_id == "c1"
    assert finding.confidence == 0.9


def test_malformed_output_falls_back_to_needs_review():
    finding = evaluate_rule(
        rule_id="SOX-302",
        title="Cert",
        regulation="SOX",
        check_prompt="certified?",
        chunks=[{"chunk_id": "c1", "text": "some filing text"}],
        llm=FakeLLM("this is not json at all"),
    )
    assert finding.status == "needs_review"
    assert finding.confidence == 0.0


def test_severity_mapping():
    assert severity_for("fail", 9) == "Critical"
    assert severity_for("fail", 6) == "High"
    assert severity_for("fail", 3) == "Medium"
    assert severity_for("fail", 1) == "Low"
    assert severity_for("pass", 10) == "Low"
    assert severity_for("needs_review", 10) == "Medium"


def test_compliance_score_aggregation():
    assert compliance_score([("pass", 5), ("pass", 5)]) == 100
    assert compliance_score([("fail", 5), ("pass", 5)]) == 50
    assert compliance_score([("fail", 10)]) == 0
    assert compliance_score([]) == 100
