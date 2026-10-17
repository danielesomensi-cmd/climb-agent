#!/bin/sh
# B386 — Vercel "Ignored Build Step" for the PWA (wired in frontend/vercel.json).
#
# Vercel runs this inside the Root Directory (frontend/). Exit codes are
# Vercel's, and they read backwards:
#   exit 0 → SKIP the build (deployment marked CANCELED)
#   exit 1 → BUILD as normal
#
# Why: ~25 of the last 40 production deploys were sync/docs/backend commits that
# rebuilt an identical PWA — and every rebuild ships a new sw.js, i.e. an update
# banner and a cache churn on every iPhone for nothing.
#
# The base is VERCEL_GIT_PREVIOUS_SHA (last SUCCESSFUL deployment of this branch,
# exposed only when an ignore step is configured), NOT `HEAD^`: a push of
# "frontend commit + sync commit" deploys only the last one, and `HEAD^..HEAD`
# would see the sync commit alone and skip the frontend change.
#
# Every doubt builds: no base (a branch's first deploy), a base missing from
# Vercel's shallow clone (depth 10), or any git error.

base="${VERCEL_GIT_PREVIOUS_SHA:-}"

if [ -z "$base" ]; then
  echo "[ignore-build] no previous deployment SHA → build"
  exit 1
fi

if ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  echo "[ignore-build] ${base} not in the clone → build"
  exit 1
fi

git diff --quiet "$base" HEAD -- .
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "[ignore-build] no change under frontend/ since ${base} → skip"
  exit 0
fi
if [ "$rc" -eq 1 ]; then
  echo "[ignore-build] frontend/ changed since ${base} → build"
else
  echo "[ignore-build] git diff failed (rc=${rc}) → build"
fi
exit 1
