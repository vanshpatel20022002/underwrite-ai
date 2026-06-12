import json
import shutil
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import DocumentChunkDB, UnderwritingCaseDB
from app.db.session import get_db
from app.schemas.case import UnderwritingCaseCreate, UnderwritingCaseResponse, UnderwritingReport
from app.workers.tasks import ingest_case_task

router = APIRouter()
settings = get_settings()


def _case_to_response(case: UnderwritingCaseDB) -> UnderwritingCaseResponse:
    raw = {k: v for k, v in case.input_data.items() if k in UnderwritingCaseCreate.model_fields}
    input_data = UnderwritingCaseCreate(**raw)
    report = UnderwritingReport(**case.report_data) if case.report_data else None
    return UnderwritingCaseResponse(
        id=case.id,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        input=input_data,
        report=report,
        ingestion_status=case.ingestion_status,
        workflow_status=case.workflow_status,
    )


@router.post("", response_model=UnderwritingCaseResponse)
async def create_case(
    address: str = Form(...),
    property_type: str = Form("single_family"),
    bedrooms: int = Form(...),
    bathrooms: float = Form(...),
    square_footage: int = Form(...),
    lot_size: float | None = Form(None),
    year_built: int | None = Form(None),
    listing_description: str = Form(""),
    borrower_notes: str = Form(""),
    appraisal_pdf: UploadFile | None = File(None),
    zoning_pdf: UploadFile | None = File(None),
    market_file: UploadFile | None = File(None),
    images: list[UploadFile] = File(default=[]),
    session: AsyncSession = Depends(get_db),
):
    case_input = UnderwritingCaseCreate(
        address=address,
        property_type=property_type,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        square_footage=square_footage,
        lot_size=lot_size,
        year_built=year_built,
        listing_description=listing_description,
        borrower_notes=borrower_notes,
    )

    case = UnderwritingCaseDB(
        id=uuid.uuid4(),
        status="created",
        input_data=case_input.model_dump(),
    )
    session.add(case)
    await session.commit()
    await session.refresh(case)

    case_dir = Path(settings.upload_dir) / str(case.id)
    case_dir.mkdir(parents=True, exist_ok=True)

    files_meta: dict = {"images": [], "appraisal_pdf": None, "zoning_pdf": None, "market_file": None}

    if appraisal_pdf and appraisal_pdf.filename:
        path = case_dir / "appraisal.pdf"
        with path.open("wb") as f:
            shutil.copyfileobj(appraisal_pdf.file, f)
        files_meta["appraisal_pdf"] = str(path)

    if zoning_pdf and zoning_pdf.filename:
        path = case_dir / "zoning.pdf"
        with path.open("wb") as f:
            shutil.copyfileobj(zoning_pdf.file, f)
        files_meta["zoning_pdf"] = str(path)

    if market_file and market_file.filename:
        ext = Path(market_file.filename).suffix or ".csv"
        path = case_dir / f"market{ext}"
        with path.open("wb") as f:
            shutil.copyfileobj(market_file.file, f)
        files_meta["market_file"] = str(path)

    for i, img in enumerate(images):
        if img.filename:
            ext = Path(img.filename).suffix or ".jpg"
            path = case_dir / f"image_{i}{ext}"
            with path.open("wb") as f:
                shutil.copyfileobj(img.file, f)
            files_meta["images"].append(str(path))

    case.input_data = {**case.input_data, "files": files_meta}
    case.ingestion_status = "queued"
    await session.commit()
    await session.refresh(case)

    ingest_case_task.delay(str(case.id))

    return _case_to_response(case)


@router.get("", response_model=list[UnderwritingCaseResponse])
async def list_cases(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(UnderwritingCaseDB).order_by(UnderwritingCaseDB.created_at.desc())
    )
    cases = result.scalars().all()
    return [_case_to_response(c) for c in cases]


@router.get("/{case_id}", response_model=UnderwritingCaseResponse)
async def get_case(case_id: UUID, session: AsyncSession = Depends(get_db)):
    case = await session.get(UnderwritingCaseDB, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_to_response(case)


@router.get("/{case_id}/chunks")
async def get_case_chunks(case_id: UUID, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(DocumentChunkDB).where(DocumentChunkDB.case_id == case_id)
    )
    chunks = result.scalars().all()
    return [
        {
            "doc_type": c.doc_type,
            "page": c.page,
            "section": c.section,
            "content": c.content[:500],
            "source_file": c.source_file,
        }
        for c in chunks
    ]
