"""Logging helpers (B285/SEC-4).

User identifiers must never appear in full in application logs. Railway log
streams are retained and broadly readable, and a leaked internal UUID is a
credential-shaped value: combined with any endpoint that trusts a raw user id,
it becomes an account-takeover vector. Log the masked prefix instead — enough
to correlate lines in a single trace, useless on its own.
"""

from __future__ import annotations

from typing import Any, Optional


def mask_uid(value: Optional[Any]) -> str:
    """Return a short, non-reversible-enough prefix of an identifier.

    ``None`` → ``'-'``. Short values are masked whole so we never echo a full
    secret by accident.
    """
    if value is None:
        return "-"
    s = str(value)
    if not s:
        return "-"
    if len(s) <= 8:
        return "***"
    return f"{s[:8]}…"
