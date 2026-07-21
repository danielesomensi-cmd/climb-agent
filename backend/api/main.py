"""Climb-agent API — FastAPI application."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.rate_limit import limiter

from backend.api.deps import DATA_DIR, USERS_DIR
from backend.api.routers import (
    admin,
    assessment,
    body_part_picker,
    catalog,
    coach,
    custom_session,
    feedback,
    free_session,
    macrocycle,
    milestones,
    mobility,
    onboarding,
    outdoor,
    plan,
    quotes,
    replanner,
    reports,
    session,
    state,
    subscription,
    tips,
    user,
    weather,
    week,
    weekly_override,
)
from backend.api.stripe_webhook import handle_stripe_webhook

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

# B165d: rate limiting on sensitive endpoints
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow Next.js dev server + Vercel production + Vercel preview branches.
# B196-CORS: regex matches any preview deployment under the climb-agent project
# (e.g. climb-agent-git-brief-foo-account.vercel.app, climb-agent-abc123-account.vercel.app)
# without opening the door to unrelated *.vercel.app sites.
#
# B285/SEC-6: the previous pattern (`climb-agent(-[a-z0-9-]+)?\.vercel\.app`)
# matched previews from ANY Vercel account — anyone could deploy a project named
# `climb-agent` and get a credentialed cross-origin channel to this API. Now
# pinned to the owning team slug, which Vercel appends to every deployment URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        # A248: climbagent.app is the canonical production domain. The old
        # climb-agent.vercel.app origin stays during the transition (Vercel
        # 308-redirects it, but cached PWA shells may still call from it).
        "https://climbagent.app",
        "https://www.climbagent.app",
        "https://climb-agent.vercel.app",
    ],
    allow_origin_regex=r"https://climb-agent-[a-z0-9-]+-danielesomensi-cmds-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# B255: gzip response compression. /api/state ships ~1.9MB uncompressed and is
# ~8.7x compressible (D241). minimum_size=1000 so tiny responses (e.g.
# /api/state/status, 29B) skip compression overhead. No streaming/SSE endpoints
# exist, so there is nothing to double-compress or break.
app.add_middleware(GZipMiddleware, minimum_size=1000)


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
app.include_router(plan.router)
app.include_router(week.router)
app.include_router(session.router)
app.include_router(replanner.router)
app.include_router(feedback.router)
app.include_router(outdoor.router)
app.include_router(free_session.router)
app.include_router(reports.router)
app.include_router(quotes.router)
app.include_router(tips.router)
app.include_router(milestones.router)
app.include_router(user.router)
app.include_router(weekly_override.router)
app.include_router(admin.router)
app.include_router(subscription.router)
app.include_router(custom_session.router)
app.include_router(body_part_picker.router)
app.include_router(mobility.router)
app.include_router(weather.router)
app.include_router(coach.router)

# Stripe webhook — registered directly to preserve raw body for signature verification
app.add_api_route(
    "/api/stripe/webhook",
    handle_stripe_webhook,
    methods=["POST"],
    tags=["subscription"],
)


@app.get("/health")
def health():
    data_dir = str(DATA_DIR)
    users_dir = str(USERS_DIR)
    is_ephemeral = "/app/backend/data" in data_dir or data_dir.endswith("backend/data")

    # Count user directories
    users_count = 0
    try:
        if os.path.isdir(users_dir):
            users_count = len([
                d for d in os.listdir(users_dir)
                if os.path.isdir(os.path.join(users_dir, d))
            ])
    except OSError:
        pass

    # Persistence marker: written once, survives redeploy if volume is real
    marker_path = os.path.join(data_dir, ".persistence_marker")
    marker_exists = os.path.isfile(marker_path)
    if not marker_exists:
        try:
            with open(marker_path, "w") as f:
                from datetime import datetime, timezone
                f.write(datetime.now(timezone.utc).isoformat())
            marker_exists = True
            marker_fresh = True
        except OSError:
            marker_fresh = True
    else:
        marker_fresh = False

    return {
        "status": "ok",
        "data_dir": data_dir,
        "data_dir_from_env": "DATA_DIR" in os.environ,
        "ephemeral_warning": is_ephemeral,
        "users_count": users_count,
        "persistence_marker_survived": not marker_fresh,
    }
