"""Telegram founder alerts — fire-and-forget push notifications.

Sends a push to the founder's Telegram chat on meaningful growth events
(new onboarding completed, trial started). Best-effort by design: every
failure is swallowed and the network call runs in a daemon thread, so a
notification can NEVER block or break the caller. This matters for two paths:

  - onboarding/complete  → must not slow down or fail the user's first request
  - stripe webhook       → must NEVER raise (a 500 makes Stripe retry; B226)

Config via env (set on Railway):
  TELEGRAM_BOT_TOKEN   bot token from @BotFather
  TELEGRAM_CHAT_ID     destination chat id (founder's private chat)

If either var is unset, notify() is a silent no-op (pytest, local dev).
Uses only the stdlib (urllib) to avoid adding a runtime dependency.
"""
from __future__ import annotations

import logging
import os
import threading
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(_API.format(token=token), data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:  # best-effort: never propagate
        logger.warning("Telegram notify failed: %s", exc)


def notify(text: str) -> None:
    """Fire-and-forget Telegram message. No-op if env unset. Never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        threading.Thread(
            target=_send, args=(token, chat_id, text), daemon=True
        ).start()
    except Exception as exc:  # thread spawn failure must not break the caller
        logger.warning("Telegram notify thread spawn failed: %s", exc)
