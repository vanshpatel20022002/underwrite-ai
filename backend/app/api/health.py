from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.health import full_health_check

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/full")
async def health_full(session: AsyncSession = Depends(get_db)):
    return await full_health_check(session)
