"""Climb-agent API — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI(title="climb-agent", version="0.1.0")

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
