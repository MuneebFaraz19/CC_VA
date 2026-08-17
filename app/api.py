"""FastAPI application — main entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import get_settings
from app.database import init_db
from app.routers import patients_router, calls_router, vapi_router

settings = get_settings()

# ── Logging ──────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising database...")
    init_db()
    logger.info("Database ready.")
    if settings.vapi_configured:
        logger.info("Vapi is configured. Webhook: %s/vapi/webhook", settings.public_base_url)
    else:
        logger.warning("Vapi API key not set — voice agent will not receive calls until configured.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Voice AI Patient Registration",
    description="Voice-based AI agent for patient demographic registration with REST API.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────
app.include_router(patients_router.router)
app.include_router(calls_router.router)
app.include_router(vapi_router.router)


# ── Health ───────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "vapi_configured": settings.vapi_configured}


# ── Dashboard (static files) ─────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the dashboard HTML."""
    index = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Voice AI Patient Registration API", "docs": "/docs", "dashboard": "/static/index.html"}
