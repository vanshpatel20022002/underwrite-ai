import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import compile_graph
from app.db.models import UnderwritingCaseDB
from app.db.session import get_db
from app.schemas.case import UnderwritingReport

router = APIRouter()


@router.post("/{case_id}/run")
async def run_workflow(case_id: UUID, session: AsyncSession = Depends(get_db)):
    case = await session.get(UnderwritingCaseDB, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.ingestion_status != "completed":
        raise HTTPException(status_code=400, detail="Ingestion not completed")

    graph = compile_graph()
    thread_id = str(case_id)
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "case_id": str(case_id),
        "input": case.input_data,
        "report": {},
    }

    case.workflow_status = "running"
    case.thread_id = thread_id
    await session.commit()

    await graph.ainvoke(initial_state, config=config)
    state = await graph.aget_state(config)

    if state.next:
        case.workflow_status = "awaiting_human_review"
        await session.commit()
        return {
            "case_id": str(case_id),
            "workflow_status": case.workflow_status,
            "message": "Human review required before final report",
        }

    result = state.values
    report = UnderwritingReport(**result.get("report", {}))
    case.report_data = report.model_dump(mode="json")
    case.workflow_status = "completed"
    case.status = "completed"
    await session.commit()

    return {"case_id": str(case_id), "workflow_status": case.workflow_status, "report": report}


@router.post("/{case_id}/resume")
async def resume_workflow(
    case_id: UUID,
    approved: bool = True,
    session: AsyncSession = Depends(get_db),
):
    case = await session.get(UnderwritingCaseDB, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    graph = compile_graph()
    config = {"configurable": {"thread_id": str(case_id)}}

    # Update state with the human decision, then resume from the interrupt point.
    await graph.aupdate_state(config, {"human_approved": approved})
    await graph.ainvoke(None, config=config)

    state = await graph.aget_state(config)
    result = state.values

    if not approved:
        case.workflow_status = "rejected"
        case.status = "rejected"
        await session.commit()
        return {"case_id": str(case_id), "workflow_status": "rejected"}

    report = UnderwritingReport(**result.get("report", {}))
    case.report_data = report.model_dump(mode="json")
    case.workflow_status = "completed"
    case.status = "completed"
    await session.commit()

    return {"case_id": str(case_id), "report": report}


@router.get("/{case_id}/stream")
async def stream_workflow(case_id: UUID, session: AsyncSession = Depends(get_db)):
    case = await session.get(UnderwritingCaseDB, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    graph = compile_graph()
    config = {"configurable": {"thread_id": str(case_id)}}

    async def event_generator():
        initial_state = {
            "case_id": str(case_id),
            "input": case.input_data,
            "report": {},
        }
        async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
