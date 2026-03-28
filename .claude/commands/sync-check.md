Pre-push verification checklist. Run all checks, report pass/fail for each.

1. **Sync status**: `python scripts/sync_status.py` — check if counters changed
2. **Test suite**: `source .venv/bin/activate && python3 -m pytest backend/tests/ -q 2>&1 | tail -5`
3. **Git status**: show untracked/unstaged files that might be forgotten
4. **Debug statements**: search for `print(`, `console.log(`, `debugger`, `breakpoint()` in tracked files (exclude tests and scripts)

Report each check as PASS or FAIL with details. Do NOT commit or push — only report.
