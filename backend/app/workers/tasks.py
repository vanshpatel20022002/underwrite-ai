import asyncio
import uuid

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def ingest_case_task(self, case_id: str) -> dict:
    from app.db.session import engine
    from app.ingestion.pipeline import run_ingestion

    async def _run():
        try:
            return await run_ingestion(uuid.UUID(case_id))
        finally:
            # Dispose the pool so the next task gets a fresh one on the new event loop.
            await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
