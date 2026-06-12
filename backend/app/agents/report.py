import json

from app.config import get_settings
from app.llm.provider import generate_structured_report
from app.retrieval.qdrant_store import hybrid_search
from app.retrieval.reranker import rerank
from app.schemas.case import Citation, Recommendation

settings = get_settings()

SYSTEM_PROMPT = """\
You are a senior real estate underwriting analyst.
Generate a lender-style underwriting memo using ONLY the provided evidence.

OUTPUT RULES — follow exactly:
1. Return ONLY a single JSON object. No markdown fences, no preamble, no explanation.
2. All string values must use JSON escape sequences: newlines as \\n, tabs as \\t.
3. Do NOT embed raw newline characters inside string values.

Required JSON keys:
- memo_markdown  : lender memo in Markdown (escape all newlines as \\n). Must include:
    * Executive Summary
    * Valuation (include the disclaimer: "Value is based on municipal assessed-value proxy, NOT a market sale price.")
    * Comparables (list top comps with address, assessed proxy, distance)
    * Adjustments table summary
    * Risk Assessment (risk score, each flag with severity)
    * Recommendation with rationale
- recommendation : exactly one of: approve | review | reject
- confidence_score: float 0.0–1.0
- key_assumptions : list of strings (include proxy-value disclosure as first item)

Never recommend approve without strong evidence. Never omit the assessed-value disclaimer."""


def build_report(
    case_id: str,
    subject: dict,
    comps: list,
    adjustments: list,
    valuation: dict,
    risk_score: float,
    risk_flags: list,
    image_notes: list,
) -> dict:
    query = f"property valuation zoning appraisal {subject.get('address', '')}"
    chunks = hybrid_search(case_id, query, doc_types=["appraisal", "zoning", "listing", "borrower"])
    ranked = rerank(query, chunks, top_k=5)

    citations = [
        Citation(
            doc_type=c["doc_type"],
            page=c.get("page"),
            section=c.get("section"),
            snippet=c["content"][:300],
            source_file=c.get("source_file", ""),
        )
        for c in ranked
    ]

    context = {
        "subject": subject,
        "comps": [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in comps],
        "adjustments": [
            a.model_dump(mode="json") if hasattr(a, "model_dump") else a for a in adjustments
        ],
        "valuation": valuation,
        "risk_score": risk_score,
        "risk_flags": [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else f for f in risk_flags
        ],
        "image_notes": [
            n.model_dump(mode="json") if hasattr(n, "model_dump") else n for n in image_notes
        ],
        "citations": [c.model_dump(mode="json") for c in citations],
    }

    user_prompt = f"""Generate underwriting report for this case:

{json.dumps(context, indent=2, default=str)}

Use citations from the citations array. Include comparable analysis and adjustment rationale."""

    try:
        llm_result = generate_structured_report(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        llm_result = {
            "memo_markdown": _fallback_memo(subject, comps, valuation, risk_flags, exc),
            "recommendation": "review",
            "confidence_score": valuation.get("confidence_score", 0.5),
        }

    confidence = float(llm_result.get("confidence_score", valuation.get("confidence_score", 0.5)))
    recommendation = llm_result.get("recommendation", "review")

    if confidence < settings.confidence_threshold:
        recommendation = Recommendation.REVIEW.value
    elif recommendation == Recommendation.APPROVE.value and confidence < settings.confidence_threshold:
        recommendation = Recommendation.REVIEW.value

    if risk_score and risk_score > 70:
        recommendation = Recommendation.REJECT.value if risk_score > 85 else Recommendation.REVIEW.value

    return {
        "estimated_value": valuation.get("estimated_value"),
        "confidence_interval": valuation.get("confidence_interval"),
        "confidence_score": confidence,
        "top_5_comps": [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in comps],
        "adjustment_table": [
            a.model_dump(mode="json") if hasattr(a, "model_dump") else a for a in adjustments
        ],
        "risk_score": risk_score,
        "risk_flags": [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else f for f in risk_flags
        ],
        "image_condition_notes": [
            n.model_dump(mode="json") if hasattr(n, "model_dump") else n for n in image_notes
        ],
        "shap_features": [
            s.model_dump(mode="json") if hasattr(s, "model_dump") else s
            for s in valuation.get("shap_features", [])
        ],
        "citations": [c.model_dump(mode="json") for c in citations],
        "memo_markdown": llm_result.get("memo_markdown", ""),
        "recommendation": recommendation,
        "raw_json": context,
    }


def _fallback_memo(subject, comps, valuation, risk_flags, exc) -> str:
    return f"""# Underwriting Memo (Fallback)

**Property:** {subject.get('address', 'N/A')}
**Estimated Value:** ${valuation.get('estimated_value', 0):,.0f}
**Comparables:** {len(comps)}
**Risk Flags:** {len(risk_flags)}

> LLM generation unavailable ({exc}). Manual review required.
"""
