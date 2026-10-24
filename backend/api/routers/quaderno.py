"""Quaderno router — the athlete's route report, shown read-only in the app (A321).

Two endpoints:

* ``GET /api/quaderno`` (Clerk auth) — does this user have a quaderno, which
  days it covers, and a fresh signed path to open it. Users without one get
  ``{"available": false}`` and the app shows nothing.
* ``GET /api/quaderno/v/{token}/{path}`` (signed link, NO bearer) — one file of
  the bundle, for the sandboxed iframe, which cannot send the Clerk token.

Reading your own data stays free (no subscription guard, as /user/export).
What is served is only what the user's current ``manifest.json`` lists, with a
CSP that sandboxes the page into an opaque origin: it can run its own scripts
and fetch its own files, nothing else — no cookies, no storage, no climbagent.app.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from backend.api.deps import get_user_id
from backend.engine import storage
from backend.engine.quaderno import (
    DAYS_PATH,
    MANIFEST_PATH,
    PAGE_PATH,
    ManifestError,
    content_type_for,
    days_from_index,
    is_safe_path,
    link_expiry,
    parse_manifest,
    sign_link,
    verify_link,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quaderno", tags=["quaderno"])

#: Who may frame the page: the app's own origins (prod, Vercel previews, dev).
FRAME_ANCESTORS = (
    "https://climbagent.app https://www.climbagent.app https://climb-agent.vercel.app "
    "https://*.vercel.app http://localhost:3000"
)


def _secret() -> Optional[str]:
    """The link-signing key. Unset → the feature is off (fail closed)."""
    return os.environ.get("QUADERNO_LINK_SECRET") or None


def _manifest(user_id: str) -> Optional[Dict[str, Any]]:
    raw = storage.read_quaderno_file(user_id, MANIFEST_PATH)
    if raw is None:
        return None
    try:
        return parse_manifest(raw)
    except ManifestError:
        logger.warning("A321: unreadable quaderno manifest for %s", user_id, exc_info=True)
        return None


@router.get("")
def get_quaderno(user_id: Optional[str] = Depends(get_user_id)):
    """Whether the user has a quaderno, its days, and a fresh signed page path."""
    secret = _secret()
    if not user_id or not secret:
        return {"available": False}
    manifest = _manifest(user_id)
    if manifest is None:
        return {"available": False}
    index = storage.read_quaderno_file(user_id, DAYS_PATH) if DAYS_PATH in manifest["files"] else None
    days = days_from_index(index) if index else []
    if not days:
        return {"available": False}
    token = sign_link(user_id, secret, int(time.time()))
    return {
        "available": True,
        "generated": manifest["generated"],
        "days": days,
        # Relative to the API origin: the app prefixes its own API base.
        "page_path": f"/api/quaderno/v/{token}/{PAGE_PATH}",
        "expires_at": link_expiry(token),
    }


def _csp(request: Request) -> str:
    # 'self' does not match reliably inside a sandboxed (opaque-origin)
    # document, so the API origin is spelled out next to it.
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    api = f"{proto}://{host}"
    return "; ".join([
        "sandbox allow-scripts",
        "default-src 'none'",
        "script-src 'unsafe-inline'",
        "style-src 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        f"img-src 'self' {api} data: blob:",
        f"connect-src 'self' {api}",
        "base-uri 'none'",
        "form-action 'none'",
        f"frame-ancestors {FRAME_ANCESTORS}",
    ])


@router.get("/v/{token}/{path:path}")
def get_quaderno_file(token: str, path: str, request: Request):
    """One file of the user's bundle, behind the signed link."""
    secret = _secret()
    user_id = verify_link(token, secret, int(time.time())) if secret else None
    if not user_id:
        raise HTTPException(status_code=403, detail="Link expired or invalid")
    if not is_safe_path(path) or path == MANIFEST_PATH:
        raise HTTPException(status_code=404, detail="Not found")
    manifest = _manifest(user_id)
    if manifest is None or path not in manifest["files"]:
        raise HTTPException(status_code=404, detail="Not found")
    data = storage.read_quaderno_file(user_id, path)
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    headers = {
        # Never cached: a new /quaderno run replaces files, and the link expires.
        "Cache-Control": "no-store",
        # The sandboxed page is an opaque origin: its fetch of data/*.json is a
        # CORS request. No credentials ride on it — the token is in the path.
        "Access-Control-Allow-Origin": "*",
        "X-Content-Type-Options": "nosniff",
        # The page loads Google Fonts: the Referer would carry the signed path.
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": _csp(request),
    }
    return Response(content=data, media_type=content_type_for(path), headers=headers)
