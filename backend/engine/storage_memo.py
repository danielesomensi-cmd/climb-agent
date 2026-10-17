"""B376 — request-scoped read-through memo for the storage layer.

A single API request used to hit the same storage read several times: a warm
``GET /api/week`` on a real state made 14 sequential Supabase round-trips, most
of them identical (``list_archived_keys`` + ``read_archived_week`` once per
resolved session, ``read_outdoor_logs`` once per guard/key consumer). Each one
is 150-470 ms in production.

This module memoises the *read* functions of the active storage backend for the
duration of ONE request:

- **Inactive by default.** Outside :func:`request_scope` (pytest direct calls,
  scripts such as ``scripts/athlete_context.py``, migrations) every decorated
  function calls straight through — identical behaviour to before.
- **Activated per request** by :class:`StorageMemoMiddleware` (``api/main.py``),
  which opens a fresh scope and drops it when the request ends: nothing is
  shared between requests or users.
- **Keyed by** ``(function, bound arguments)`` — the user id is the first
  argument of every memoised read, so it is part of the key.
- **Any write invalidates.** Every storage write (state, archive, outdoor log,
  deletes) clears the whole memo of the request, before and after the write.
  Conservative on purpose: a request has at most a handful of writes.
- **Callers never share an object with the memo.** The value is snapshotted as
  JSON when stored and every hit returns a fresh ``json.loads`` of it, so a
  caller that mutates what it got cannot poison a later read. The first (miss)
  call returns the backend's own fresh object. JSON round-trip is exact for
  these payloads (they come from JSON — a JSONB column or a ``.json`` file) and
  several times cheaper than ``copy.deepcopy``; non-JSON values fall back to
  ``deepcopy``.
- **Kill switch:** ``STORAGE_REQUEST_MEMO=0`` (read at call time) turns the memo
  off without a deploy. Only the literal ``0`` disables.

Engine modules are untouched: they keep calling ``storage.<fn>`` as before.
"""

from __future__ import annotations

import contextvars
import copy
import functools
import inspect
import json
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

_MISSING = object()

# The memo of the current request: {key: ("json", str) | ("deep", obj)}, or
# None outside a request scope.
_memo: contextvars.ContextVar[Optional[Dict[Tuple, Tuple[str, Any]]]] = contextvars.ContextVar(
    "storage_request_memo", default=None
)


def _enabled() -> bool:
    return os.environ.get("STORAGE_REQUEST_MEMO", "1") != "0"


def is_active() -> bool:
    """True inside a request scope with the memo enabled."""
    return _memo.get() is not None and _enabled()


@contextmanager
def request_scope() -> Iterator[None]:
    """Open a fresh memo for the enclosed work (one API request)."""
    token = _memo.set({})
    try:
        yield
    finally:
        _memo.reset(token)


def invalidate() -> None:
    """Drop every memoised read of the current scope (no-op outside one)."""
    memo = _memo.get()
    if memo is not None:
        memo.clear()


def _snapshot(value: Any) -> Tuple[str, Any]:
    try:
        return ("json", json.dumps(value))
    except (TypeError, ValueError):
        return ("deep", copy.deepcopy(value))


def _restore(snap: Tuple[str, Any]) -> Any:
    kind, payload = snap
    if kind == "json":
        return json.loads(payload)
    return copy.deepcopy(payload)


def memo_read(fn: Callable) -> Callable:
    """Decorate a storage read: memoised inside a request scope.

    The wrapper calls ``wrapper.__wrapped__`` at call time, so a test can spy on
    the real backend I/O by patching that attribute.
    """
    sig = inspect.signature(fn)
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        target = wrapper.__wrapped__
        memo = _memo.get()
        if memo is None or not _enabled():
            return target(*args, **kwargs)
        try:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            key = (name, tuple(bound.arguments.items()))
            hash(key)
        except TypeError:
            return target(*args, **kwargs)
        snap = memo.get(key, _MISSING)
        if snap is not _MISSING:
            return _restore(snap)
        value = target(*args, **kwargs)
        memo[key] = _snapshot(value)
        return value

    return wrapper


def memo_write(fn: Callable) -> Callable:
    """Decorate a storage write: clears the request memo before and after."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        invalidate()
        try:
            return wrapper.__wrapped__(*args, **kwargs)
        finally:
            invalidate()

    return wrapper


class StorageMemoMiddleware:
    """Pure ASGI middleware: one memo scope per HTTP request.

    Pure ASGI (not ``BaseHTTPMiddleware``) so the scope lives in the same task
    as the endpoint; sync endpoints run in a threadpool with a *copy* of the
    context, which still points at the same memo dict.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        with request_scope():
            await self.app(scope, receive, send)
