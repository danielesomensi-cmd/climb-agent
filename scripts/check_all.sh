#!/usr/bin/env bash
set -euo pipefail
python scripts/check_repo_integrity.py
python scripts/audit_vocabulary.py
python -m py_compile catalog/engine/resolve_session.py
python -m pytest -q
python scripts/run_baseline_session.py
