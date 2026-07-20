"""RAG compliance engine (R4): retrieved chunks + rule prompt -> structured finding.

Structured output is Pydantic-enforced; malformed LLM output is retried once and
then downgraded to needs_review. A rule is never silently dropped.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings


class Evidence(BaseModel):
    chunk_id: str
    quote: str

class RuleFinding(BaseModel):
    rule_id: str
    status: Literal["pass", "fail", "needs_review"]
    evidence: list[Evidence] = []
    explanation: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    reasoning: str = ""      # NEW: model thinking trace (not from the JSON)



PROMPT_TEMPLATE = """You are a meticulous financial compliance auditor.

Rule under evaluation:
- Title: {title}
- Regulation: {regulation}
- Check: {check_prompt}

Filing excerpts (each prefixed with its chunk_id in brackets):
{context}

Evaluate whether the filing satisfies this rule based ONLY on the excerpts above.
Respond with ONLY a JSON object, no prose, matching exactly:
{{"status": "pass" | "fail" | "needs_review", "evidence": [{{"chunk_id": "...", "quote": "..."}}], "explanation": "...", "confidence": 0.0}}
"""


def get_llm():
    """Provider factory switchable via LLM_PROVIDER env var."""
    s = get_settings()
    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o", api_key=s.openai_api_key, temperature=0)
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-5", api_key=s.anthropic_api_key, temperature=0)
    # default: NVIDIA NIM (Nemotron 3 Ultra)
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    return ChatNVIDIA(
        model=s.chat_model,
        api_key=s.nvidia_api_key,
        temperature=s.chat_temperature,
        top_p=s.chat_top_p,
        max_tokens=s.reasoning_budget + 2048,
        model_kwargs={
            "reasoning_budget": s.reasoning_budget,
            "chat_template_kwargs": {"enable_thinking": s.enable_thinking},
        },
    )



def _extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in LLM output")
    return json.loads(content[start : end + 1])


def evaluate_rule(
    *,
    rule_id: str,
    title: str,
    regulation: str,
    check_prompt: str,
    chunks: list[dict],
    llm=None,
) -> RuleFinding:
    llm = llm if llm is not None else get_llm()
    context = "\n\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks) or "(no excerpts found)"
    prompt = PROMPT_TEMPLATE.format(
        title=title, regulation=regulation, check_prompt=check_prompt, context=context
    )
    for _attempt in range(2):  # one retry on malformed output
        try:
            raw = llm.invoke(prompt)
            content = raw.content if hasattr(raw, "content") else str(raw)
            reasoning = ""
            if hasattr(raw, "additional_kwargs"):
                reasoning = (raw.additional_kwargs.get("reasoning_content") or "")[:4000]
            data = _extract_json(content)
            data["rule_id"] = rule_id
            finding = RuleFinding.model_validate(data)
            finding.reasoning = reasoning
            return finding
        except Exception:
            continue
    return RuleFinding(
        rule_id=rule_id,
        status="needs_review",
        explanation="LLM output could not be parsed after retry; manual review required.",
        confidence=0.0,
    )
