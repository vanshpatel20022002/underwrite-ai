import httpx
from qdrant_client import QdrantClient
from redis import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


async def check_postgres(session: AsyncSession) -> dict:
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_redis() -> dict:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.redis_url)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_qdrant() -> dict:
    settings = get_settings()
    try:
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        collections = client.get_collections()
        return {"status": "ok", "collections": len(collections.collections)}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def full_health_check(session: AsyncSession) -> dict:
    postgres = await check_postgres(session)
    redis = check_redis()
    qdrant = check_qdrant()
    overall = (
        "ok"
        if all(s["status"] == "ok" for s in [postgres, redis, qdrant])
        else "degraded"
    )
    return {
        "status": overall,
        "services": {
            "postgres": postgres,
            "redis": redis,
            "qdrant": qdrant,
        },
    }
