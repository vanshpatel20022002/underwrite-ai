import uuid
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.db.models import DocumentChunkDB, UnderwritingCaseDB
from app.db.session import async_session_factory
from app.geo.geocoder import geocode_address
from app.ingestion.market_loader import load_market_file
from app.ingestion.pdf_parser import extract_pdf_chunks
from app.retrieval.qdrant_store import index_chunks

settings = get_settings()


async def run_ingestion(case_id: uuid.UUID) -> dict:
    async with async_session_factory() as session:
        case = await session.get(UnderwritingCaseDB, case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")

        await session.execute(
            update(UnderwritingCaseDB)
            .where(UnderwritingCaseDB.id == case_id)
            .values(ingestion_status="processing")
        )
        await session.commit()

        files = case.input_data.get("files", {})
        all_chunks: list[dict] = []

        if appraisal := files.get("appraisal_pdf"):
            all_chunks.extend(extract_pdf_chunks(appraisal, "appraisal"))

        if zoning := files.get("zoning_pdf"):
            all_chunks.extend(extract_pdf_chunks(zoning, "zoning"))

        if listing := case.input_data.get("listing_description"):
            all_chunks.append(
                {
                    "doc_type": "listing",
                    "page": None,
                    "section": "description",
                    "content": listing,
                    "source_file": "listing",
                }
            )

        if notes := case.input_data.get("borrower_notes"):
            all_chunks.append(
                {
                    "doc_type": "borrower",
                    "page": None,
                    "section": "notes",
                    "content": notes,
                    "source_file": "borrower_notes",
                }
            )

        market_stats = None
        if market_path := files.get("market_file"):
            market_stats = load_market_file(market_path)

        for chunk in all_chunks:
            db_chunk = DocumentChunkDB(
                case_id=case_id,
                doc_type=chunk["doc_type"],
                page=chunk.get("page"),
                section=chunk.get("section"),
                content=chunk["content"],
                source_file=chunk["source_file"],
            )
            session.add(db_chunk)

        await session.commit()

        if all_chunks:
            await index_chunks(str(case_id), all_chunks)

        if not case.input_data.get("latitude"):
            lat, lon = await geocode_address(case.input_data["address"])
            if lat and lon:
                case.input_data = {**case.input_data, "latitude": lat, "longitude": lon}

        if market_stats:
            case.input_data = {**case.input_data, "market_stats": market_stats["stats"]}

        case.ingestion_status = "completed"
        case.input_data = {**case.input_data, "chunk_count": len(all_chunks)}
        await session.commit()

        return {
            "case_id": str(case_id),
            "chunks_indexed": len(all_chunks),
            "market_stats": market_stats,
            "ingestion_status": "completed",
        }
