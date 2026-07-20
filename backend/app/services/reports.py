"""Audit report rendering (R6): JSON structure + PDF export."""

from jinja2 import Template

REPORT_HTML = Template(
    """<html><head><style>
body { font-family: Helvetica, sans-serif; margin: 32px; }
h1 { font-size: 20px; } table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 11px; text-align: left; }
.sev-Critical { color: #b91c1c; font-weight: bold; } .sev-High { color: #c2410c; }
.sev-Medium { color: #a16207; } .sev-Low { color: #15803d; }
.score { font-size: 32px; font-weight: bold; }
</style></head><body>
<h1>Compliance Audit Report - {{ r.ticker }} {{ r.filing_type }} {{ r.fiscal_quarter }} FY{{ r.fiscal_year }}</h1>
<p>Audit run: {{ r.audit_run_id }} | Model: {{ r.model_name }} | Status: {{ r.status }}</p>
<p class=\"score\">Score: {{ r.compliance_score }}</p>
<table><tr><th>Rule</th><th>Status</th><th>Severity</th><th>Confidence</th><th>Explanation</th><th>Evidence</th></tr>
{% for f in r.findings %}<tr>
<td>{{ f.rule_id }}</td><td>{{ f.status }}</td>
<td class=\"sev-{{ f.severity }}\">{{ f.severity }}</td>
<td>{{ '%.2f'|format(f.confidence) }}</td><td>{{ f.explanation }}</td>
<td>{% for e in f.evidence %}<em>[{{ e.chunk_id }}]</em> {{ e.quote }}<br/>{% endfor %}</td>
</tr>{% endfor %}</table>
</body></html>"""
)


def report_json(run, filing, findings) -> dict:
    return {
        "audit_run_id": run.id,
        "filing_id": filing.id,
        "ticker": filing.ticker,
        "filing_type": filing.filing_type,
        "fiscal_year": filing.fiscal_year,
        "fiscal_quarter": filing.fiscal_quarter,
        "status": run.status,
        "compliance_score": run.compliance_score,
        "model_name": run.model_name,
        "rule_versions": run.rule_versions or {},
        "findings": [
            {
                "rule_id": f.rule_id,
                "status": f.status,
                "severity": f.severity,
                "confidence": f.confidence,
                "explanation": f.explanation,
                "evidence": f.evidence or [],
            }
            for f in findings
        ],
    }


class _Obj:
    def __init__(self, d: dict):
        for k, v in d.items():
            if k == "findings":
                v = [_Obj(x) for x in v]
            elif k == "evidence":
                v = [_Obj(x) for x in v]
            setattr(self, k, v)


def render_pdf(report: dict) -> bytes:
    from weasyprint import HTML  # lazy: heavy native deps

    html = REPORT_HTML.render(r=_Obj(report))
    return HTML(string=html).write_pdf()
