"""The athlete's own route report ("quaderno"), hosted read-only (A321).

The quaderno is an interactive page built OUTSIDE climb-agent (Daniele's
climb-watch repo: route drawings, per-second charts, beta). climb-agent does
not draw anything: ``scripts/sync_quaderno.py`` copies the published bundle
into the user's private storage, and the app shows the page itself in a
sandboxed iframe, opened on the tapped crag day. One drawing, always aligned.

This module is the pure half — no I/O, no clock, no env:

* the bundle's ``manifest.json`` (contract ``climb-watch/report-manifest@1``,
  climb-watch ``docs/REPORT_DATA.md``): parsing, the sync plan, which paths may
  be served and as what;
* the signed link. The iframe cannot send the Clerk bearer token, so the
  backend hands out a short-lived HMAC token that carries the user id. It sits
  in the URL PATH, not the query: the page loads ``data/...`` relatively, and a
  relative URL drops the page's query string.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from typing import Any, Dict, List, Optional

MANIFEST_PATH = "manifest.json"
MANIFEST_SCHEMA = "climb-watch/report-manifest@1"
#: The page the iframe opens (skeleton + page, written by climb-watch).
PAGE_PATH = "standalone.html"
#: The day index inside the bundle: ``{"generated", "days": [{"date", ...}]}``.
DAYS_PATH = "data/days.json"

#: Served types. Anything else in a manifest is refused, never guessed.
CONTENT_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

#: One path segment: letters, digits, dot, dash, underscore; never a dotfile.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: A link lives this long. The app asks for a fresh one each time the viewer
#: opens, so it only has to outlast one look at the page.
LINK_TTL_SECONDS = 60 * 60


class ManifestError(ValueError):
    """The bundle's manifest is missing, malformed or lists an unsafe path."""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def content_type_for(path: str) -> Optional[str]:
    """The Content-Type a bundle path is served with, or None (never served)."""
    dot = path.rfind(".")
    if dot < 0:
        return None
    return CONTENT_TYPES.get(path[dot:].lower())


def is_safe_path(path: Any) -> bool:
    """A relative bundle path that cannot leave the user's folder.

    No absolute path, no ``..``, no backslash, no empty segment, no dotfile,
    and a type from CONTENT_TYPES. Checked on upload AND on every read.
    """
    if not isinstance(path, str) or not path or len(path) > 200:
        return False
    segments = path.split("/")
    if any(not _SEGMENT_RE.match(s) or s in {".", ".."} for s in segments):
        return False
    return content_type_for(path) is not None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def parse_manifest(raw: bytes) -> Dict[str, Any]:
    """Parse and validate a manifest. Raises ManifestError.

    Returns ``{"generated": str, "files": {path: {"bytes": int, "sha256": str}}}``.
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ManifestError(f"manifest is not JSON: {e}") from e
    if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError(f"manifest schema is not {MANIFEST_SCHEMA}")
    generated = data.get("generated")
    if not isinstance(generated, str) or not generated:
        raise ManifestError("manifest has no 'generated'")
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest lists no files")
    files: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ManifestError("manifest entry is not an object")
        path = entry.get("path")
        if not is_safe_path(path) or path == MANIFEST_PATH:
            raise ManifestError(f"manifest lists an unsafe path: {path!r}")
        size, sha = entry.get("bytes"), entry.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ManifestError(f"bad 'bytes' for {path}")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha):
            raise ManifestError(f"bad 'sha256' for {path}")
        if path in files:
            raise ManifestError(f"manifest lists {path} twice")
        files[path] = {"bytes": size, "sha256": sha}
    if PAGE_PATH not in files:
        raise ManifestError(f"manifest does not list {PAGE_PATH}")
    return {"generated": generated, "files": files}


def plan_sync(
    local: Dict[str, Any], remote: Optional[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """What a sync must do to make the stored bundle equal the local one.

    ``upload``: new or changed files (by sha256). ``delete``: stored files the
    new manifest no longer lists. The caller uploads first, the manifest LAST,
    then deletes — so a sync that stops half-way still serves one consistent
    version (the old manifest only lists files that are still there).
    """
    remote_files = (remote or {}).get("files") or {}
    upload, unchanged = [], []
    for path, meta in sorted(local["files"].items()):
        if (remote_files.get(path) or {}).get("sha256") == meta["sha256"]:
            unchanged.append(path)
        else:
            upload.append(path)
    delete = sorted(p for p in remote_files if p not in local["files"])
    return {"upload": upload, "delete": delete, "unchanged": unchanged}


def days_from_index(raw: bytes) -> List[str]:
    """The dates the quaderno has a page for, newest first, from days.json.

    A malformed index yields no days (the viewer simply is not offered).
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return []
    days = data.get("days") if isinstance(data, dict) else None
    if not isinstance(days, list):
        return []
    dates = {
        d.get("date") for d in days
        if isinstance(d, dict) and isinstance(d.get("date"), str) and _DATE_RE.match(d["date"])
    }
    return sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Signed link
# ---------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(secret: str, payload: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return _b64(mac.digest())


def sign_link(user_id: str, secret: str, now: int, ttl: int = LINK_TTL_SECONDS) -> str:
    """A path-safe token ``<b64 user id>.<expiry>.<signature>``."""
    if not user_id or not secret:
        raise ValueError("sign_link needs a user id and a secret")
    payload = f"{_b64(user_id.encode('utf-8'))}.{int(now) + int(ttl)}"
    return f"{payload}.{_signature(secret, payload)}"


def verify_link(token: str, secret: str, now: int) -> Optional[str]:
    """The user id a token was issued for, or None (bad, tampered, expired)."""
    if not token or not secret:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    uid_b64, exp_text, sig = parts
    payload = f"{uid_b64}.{exp_text}"
    if not hmac.compare_digest(sig, _signature(secret, payload)):
        return None
    if not exp_text.isdigit() or int(exp_text) < int(now):
        return None
    try:
        user_id = _unb64(uid_b64).decode("utf-8")
    except (binascii.Error, ValueError):
        return None
    return user_id or None


def link_expiry(token: str) -> int:
    """The expiry (epoch seconds) written in a token made by sign_link."""
    return int(token.split(".")[1])
