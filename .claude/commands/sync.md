Run the status sync script and commit:

1. Commit your brief's work first: `sync_status.py` aborts if non-sync files are dirty.
2. Run: `python scripts/sync_status.py`
3. Review the output: it must end with "✅ All validations passed." — read any ⚠️ warning.
4. If anything changed, commit only the synced files (no brief id in the subject):
   ```bash
   git commit -m "sync: contatori" -- PROJECT_BRIEF.md README.md CLAUDE.md docs/API_ENDPOINTS.md docs/FRONTEND.md
   ```
   (pass only the paths that actually changed — `git status --short` shows them)

Do NOT manually edit counters in any file.
The sync script is the single source of truth for all project metrics:
tests/exercises/sessions/templates/endpoints/pages/components in `PROJECT_BRIEF.md` + `README.md`,
router count in `CLAUDE.md`, endpoint total in `docs/API_ENDPOINTS.md`, page count in `docs/FRONTEND.md` (layout since D285).
The endpoint TABLE rows in `docs/API_ENDPOINTS.md` are edited by hand; sync only warns on a row-count mismatch.
The pre-push hook runs the same script and blocks the push if counters are stale.
