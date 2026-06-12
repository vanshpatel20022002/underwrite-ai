from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.agents.report import build_report
from app.agents.risk import analyze_images, evaluate_risk
from app.config import get_settings
from app.db.session import async_session_factory
from app.geo.comp_search import compute_adjustments, search_comparables
from app.ml.ranker import rank_comparables
from app.schemas.case import AdjustmentRow, ComparableSale, Recommendation

settings = get_settings()
_checkpointer = MemorySaver()


class AgentState(TypedDict, total=False):
    case_id: str
    input: dict
    comps: list
    adjustments: list
    valuation: dict
    risk_score: float
    risk_flags: list
    image_notes: list
    report: dict
    human_approved: bool
    workflow_status: str
    messages: Annotated[list, add_messages]


async def ingestion_node(state: AgentState) -> dict:
    return {"workflow_status": "ingestion_complete"}


async def comp_search_node(state: AgentState) -> dict:
    from app.geo.geocoder import geocode_address

    subject = dict(state["input"])
    if not subject.get("latitude") or not subject.get("longitude"):
        lat, lon = await geocode_address(subject["address"])
        if lat and lon:
            subject["latitude"] = lat
            subject["longitude"] = lon

    async with async_session_factory() as session:
        comps = await search_comparables(session, subject, radius_miles=5.0, limit=20)

    ranked = rank_comparables(subject, comps)
    top5 = ranked[:5]

    all_adjustments: list[AdjustmentRow] = []
    for comp in top5:
        _, adj = compute_adjustments(subject, comp)
        all_adjustments.extend(adj)

    return {
        "comps": top5,
        "adjustments": all_adjustments,
        "input": subject,
        "workflow_status": "comps_complete",
    }


async def valuation_node(state: AgentState) -> dict:
    from app.ml.predict import predict_value

    subject = state["input"]
    try:
        valuation = predict_value(subject)
        if hasattr(valuation.get("confidence_interval"), "model_dump"):
            valuation["confidence_interval"] = valuation["confidence_interval"].model_dump()
        valuation["shap_features"] = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in valuation.get("shap_features", [])
        ]
    except FileNotFoundError:
        comps = state.get("comps", [])
        if comps:
            prices = [c.adjusted_price or c.sale_price for c in comps]
            median = sorted(prices)[len(prices) // 2]
            valuation = {
                "estimated_value": median,
                "confidence_interval": {"low": median * 0.9, "high": median * 1.1, "level": 0.8},
                "confidence_score": 0.5,
                "shap_features": [],
            }
        else:
            valuation = {
                "estimated_value": None,
                "confidence_score": 0.3,
                "shap_features": [],
            }

    return {"valuation": valuation, "workflow_status": "valuation_complete"}


async def risk_node(state: AgentState) -> dict:
    subject = state["input"]
    files = subject.get("files", {})
    image_paths = files.get("images", [])
    image_notes = analyze_images(image_paths)

    has_zoning = bool(files.get("zoning_pdf"))
    comps = state.get("comps", [])
    valuation = state.get("valuation", {})

    comps_typed = []
    for c in comps:
        if isinstance(c, ComparableSale):
            comps_typed.append(c)
        elif isinstance(c, dict):
            comps_typed.append(ComparableSale(**c))

    risk_score, risk_flags = evaluate_risk(
        subject,
        comps_typed,
        valuation.get("estimated_value"),
        image_notes,
        has_zoning,
    )

    return {
        "risk_score": risk_score,
        "risk_flags": [f.model_dump() for f in risk_flags],
        "image_notes": [n.model_dump() for n in image_notes],
        "workflow_status": "risk_complete",
    }


async def human_review_node(state: AgentState) -> dict:
    if state.get("human_approved") is not None:
        return {"workflow_status": "human_review_complete"}
    return {"workflow_status": "awaiting_human_review"}


def should_continue_after_human(state: AgentState) -> str:
    if state.get("human_approved") is None and state.get("workflow_status") == "awaiting_human_review":
        return "interrupt"
    return "report"


async def report_node(state: AgentState) -> dict:
    comps = state.get("comps", [])
    comps_typed = []
    for c in comps:
        if isinstance(c, dict):
            comps_typed.append(ComparableSale(**c))
        else:
            comps_typed.append(c)

    adjustments = state.get("adjustments", [])
    risk_flags = state.get("risk_flags", [])
    image_notes = state.get("image_notes", [])

    from app.schemas.case import ImageConditionNote, RiskFlag

    report = build_report(
        case_id=state["case_id"],
        subject=state["input"],
        comps=comps_typed,
        adjustments=adjustments,
        valuation=state.get("valuation", {}),
        risk_score=state.get("risk_score", 50),
        risk_flags=[RiskFlag(**f) if isinstance(f, dict) else f for f in risk_flags],
        image_notes=[ImageConditionNote(**n) if isinstance(n, dict) else n for n in image_notes],
    )

    confidence = report.get("confidence_score", 0.5)
    if confidence < settings.confidence_threshold and report.get("recommendation") == "approve":
        report["recommendation"] = Recommendation.REVIEW.value

    return {"report": report, "workflow_status": "completed"}


def compile_graph():
    graph = StateGraph(AgentState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("comp_search", comp_search_node)
    graph.add_node("valuation", valuation_node)
    graph.add_node("risk", risk_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "comp_search")
    graph.add_edge("comp_search", "valuation")
    graph.add_edge("valuation", "risk")
    graph.add_edge("risk", "human_review")
    graph.add_edge("human_review", "report")
    graph.add_edge("report", END)

    return graph.compile(
        checkpointer=_checkpointer,
        interrupt_before=["report"],
    )


def get_checkpointer():
    return _checkpointer
