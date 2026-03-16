"""Centralised persistence layer for climb-agent.

Dispatches to the active backend based on STORAGE_BACKEND env var:
  - 'file'     (default) → storage_file.py   (JSON/JSONL on disk)
  - 'supabase'           → storage_supabase.py (Postgres JSONB)

All consumers import from this module — the backend is transparent.
This module replaces itself in sys.modules with the chosen backend so that
monkeypatching (e.g. in tests) propagates directly to the implementation.
"""

import os as _os
import sys as _sys

_BACKEND = _os.environ.get("STORAGE_BACKEND", "file")

if _BACKEND == "supabase":
    import backend.engine.storage_supabase as _impl
else:
    import backend.engine.storage_file as _impl

# Replace this module with the backend implementation.
# All attribute access (including monkeypatch in tests) goes directly
# to the backend module — no stale copies.
_impl.__name__ = __name__
_impl.__package__ = __package__
_sys.modules[__name__] = _impl
