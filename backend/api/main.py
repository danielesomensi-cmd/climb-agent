"""Climb-agent API — FastAPI application."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    week,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="climb-agent", version="0.1.0")

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


@app.get("/health")
def health():
    return {"status": "ok"}
