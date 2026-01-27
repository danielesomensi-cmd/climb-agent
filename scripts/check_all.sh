#!/usr/bin/env bash
set -euo pipefail
python scripts/check_repo_integrity.py
python scripts/audit_vocabulary.py
python -m py_compile catalog/engine/resolve_session.py
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_baseline_session.py
