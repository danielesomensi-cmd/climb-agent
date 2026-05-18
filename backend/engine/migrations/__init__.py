"""Lazy on-read migrations for user_state schema evolution.

Each migration exposes a single function `migrate(state) -> bool` that mutates
``state`` in place and returns True iff the state was modified (so the caller
can persist it).

Conventions:
- Idempotent: running the same migration twice must not change state the
  second time.
- Read-tolerant: missing keys must be silently accepted (legacy states are
  the whole point of migrations).
- No assumptions about ordering: each migration must be safe to run in
  isolation against any prior state.
"""
