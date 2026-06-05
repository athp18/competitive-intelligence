import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from api.routers import alerts, query, reports, runs, signals, targets

log = structlog.get_logger()

settings = get_settings()

app = FastAPI(
    title="Competitive Intelligence Engine",
    version="0.1.0",
    description="Multi-agent competitive intelligence platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(targets.router)
app.include_router(signals.router)
app.include_router(reports.router)
app.include_router(runs.router)
app.include_router(query.router)
app.include_router(alerts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    from db.models import get_session_factory
    from db.queries import get_metrics
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await get_metrics(session)


@app.on_event("startup")
async def startup():
    log.info("cie_api_starting", version="0.1.0")
