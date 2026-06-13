import json

from app.config import get_settings
from app.llm.provider import generate_structured_report
from app.retrieval.qdrant_store import hybrid_search
from app.retrieval.reranker import rerank
from app.schemas.case import Citation, Recommendation

settings = get_settings()

SYSTEM_PROMPT = """\
You are a senior real estate underwriting analyst. Write a concise, professional lender-style underwriting memo.

OUTPUT RULES — follow exactly:
1. Return ONLY a single JSON object. No markdown fences, no preamble, no explanation.
2. All string values must use JSON escape sequences: newlines as \\n, tabs as \\t.
3. Do NOT embed raw newline characters inside string values.
4. Do NOT use markdown tables anywhere in memo_markdown. Use bullet lists instead.
5. Do NOT include any citation page references (no "p.?", no "p.1", no "listing p.", no "doc p.X").

Required JSON keys:
- memo_markdown  : lender memo in Markdown (escape all newlines as \\n).
    Use EXACTLY these section headers in this order:

    ## Executive Summary
    2-3 sentences: property address, estimated value, overall recommendation.

    ## Valuation
    Estimated value, confidence interval, confidence score.
    Always include this exact sentence: "Value is based on municipal assessed-value proxy data, NOT a market sale price."

    ## Comparable Sales
    Bullet list only — no tables. Each bullet: address, assessed proxy value, distance.
    Example: "- 123 Main St: $420,000 assessed proxy, 0.3 mi"

    ## Adjustments
    Bullet list only — no tables. Group by comp ID.
    Example: "- Comp C001 | GLA: subject 1,800 sqft vs comp 2,100 sqft → -$9,000"

    ## Risk Assessment
    Risk score out of 100. Bullet list of each risk flag with [SEVERITY] label and one-line explanation.

    ## Recommendation
    State the recommendation (approve / review / reject) and explain WHY with 2-3 specific data points
    from the case (e.g., confidence score, risk score, specific risk flags, or comp spread).
    Do not use vague language. Be direct.

    ## Data Limitation
    This estimate is based on municipal assessed-value proxy data, not actual transaction sale prices.

- recommendation : exactly one of: approve | review | reject
- confidence_score: float 0.0–1.0
- key_assumptions : list of strings

Keep the memo under 500 words. Never omit any section header. Never recommend approve without strong evidence."""


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
    address = subject.get("address", "N/A")
    est_value = valuation.get("estimated_value", 0) or 0
    ci = valuation.get("confidence_interval") or {}
    ci_low = ci.get("low", 0)
    ci_high = ci.get("high", 0)
    confidence = valuation.get("confidence_score", 0.5) or 0.5

    comp_bullets = "\n".join(
        f"- {c.get('address', 'N/A')}: ${c.get('sale_price', 0):,.0f} assessed proxy, "
        f"{c.get('distance_miles', 0):.1f} mi"
        for c in (comps[:5] if comps else [])
    ) or "- No comparables available."

    flag_bullets = "\n".join(
        f"- [{f.get('severity', 'UNKNOWN').upper()}] {f.get('message', '')}"
        for f in (risk_flags if risk_flags else [])
    ) or "- No risk flags identified."

    return (
        f"## Executive Summary\n\n"
        f"Property at {address} has an estimated value of ${est_value:,.0f}. "
        f"Automated report generation was unavailable; manual review is required.\n\n"
        f"## Valuation\n\n"
        f"- Estimated Value: ${est_value:,.0f}\n"
        f"- Confidence Interval: ${ci_low:,.0f} – ${ci_high:,.0f}\n"
        f"- Confidence Score: {confidence * 100:.0f}%\n\n"
        f"Value is based on municipal assessed-value proxy data, NOT a market sale price.\n\n"
        f"## Comparable Sales\n\n"
        f"{comp_bullets}\n\n"
        f"## Adjustments\n\n"
        f"- Adjustments not computed; LLM unavailable.\n\n"
        f"## Risk Assessment\n\n"
        f"{flag_bullets}\n\n"
        f"## Recommendation\n\n"
        f"**Review required.** Automated LLM generation failed ({type(exc).__name__}). "
        f"Confidence score ({confidence * 100:.0f}%) and {len(risk_flags)} risk flag(s) "
        f"require manual underwriter assessment before any credit decision.\n\n"
        f"## Data Limitation\n\n"
        f"This estimate is based on municipal assessed-value proxy data, not actual transaction sale prices."
    )
