"""Climb-agent API — FastAPI application."""

import logging
import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.deps import DATA_DIR, USERS_DIR
from backend.api.routers import (
    assessment,
    catalog,
    feedback,
    macrocycle,
    onboarding,
    outdoor,
    quotes,
    replanner,
    reports,
    session,
    state,
    user,
    week,
)

logger = logging.getLogger(__name__)


def _check_data_dir() -> None:
    """Log DATA_DIR path at startup and verify it is writable."""
    data_dir = str(DATA_DIR)
    users_dir = str(USERS_DIR)
    is_ephemeral = "/app/backend/data" in data_dir or data_dir.endswith("backend/data")

    logger.warning("=" * 60)
    logger.warning("DATA_DIR  = %s", data_dir)
    logger.warning("USERS_DIR = %s", users_dir)
    logger.warning("DATA_DIR env var set: %s", "DATA_DIR" in os.environ)

    if is_ephemeral:
        logger.warning(
            "⚠️  DATA_DIR points to ephemeral filesystem! "
            "User data WILL BE LOST on redeploy. "
            "Set DATA_DIR env var to a persistent volume path."
        )

    # Verify writable
    os.makedirs(data_dir, exist_ok=True)
    try:
        probe = os.path.join(data_dir, ".write_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        logger.warning("DATA_DIR writable: YES")
    except OSError as e:
        logger.error("DATA_DIR writable: NO — %s", e)

    logger.warning("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_data_dir()
    yield


app = FastAPI(title="climb-agent", version="0.1.0", lifespan=lifespan)

# CORS — allow Next.js dev server + Vercel production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://climb-agent.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean JSON error."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Mount routers
app.include_router(state.router)
app.include_router(catalog.router)
app.include_router(onboarding.router)
app.include_router(assessment.router)
app.include_router(macrocycle.router)
app.include_router(week.router)
app.include_router(session.router)
app.include_router(replanner.router)
app.include_router(feedback.router)
app.include_router(outdoor.router)
app.include_router(reports.router)
app.include_router(quotes.router)
app.include_router(user.router)


@app.get("/health")
def health():
    data_dir = str(DATA_DIR)
    is_ephemeral = "/app/backend/data" in data_dir or data_dir.endswith("backend/data")
    return {
        "status": "ok",
        "data_dir": data_dir,
        "data_dir_from_env": "DATA_DIR" in os.environ,
        "ephemeral_warning": is_ephemeral,
    }
