from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api import cases, eval, health, workflow
from app.config import get_settings
from app.db.init_db import init_db
from app.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry()
    await init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="Real Estate Underwriting AI",
    description="Agentic property underwriting with comps, ML valuation, and cited reports",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(cases.router, prefix="/api/v1/cases", tags=["cases"])
app.include_router(workflow.router, prefix="/api/v1/workflow", tags=["workflow"])
app.include_router(eval.router, prefix="/api/v1/eval", tags=["eval"])

FastAPIInstrumentor.instrument_app(app)
