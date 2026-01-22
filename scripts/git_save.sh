#!/usr/bin/env bash
set -euo pipefail

MSG="${1:-}"
if [[ -z "${MSG}" ]]; then
  echo "Usage: scripts/git_save.sh \"commit message\""
  exit 1
fi

echo "== status =="
git status -sb

echo "== pull (ff-only) =="
git pull --ff-only

echo "== compile =="
python -m py_compile catalog/engine/resolve_session.py

echo "== tests =="
python -m unittest discover -s tests -p "test_*.py" -v

echo "== diff stat =="
git diff --stat || true

echo "== commit + push =="
git add -A
git commit -m "$MSG"
git push

echo "OK: pushed"
