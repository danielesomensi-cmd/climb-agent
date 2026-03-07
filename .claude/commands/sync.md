Run the status sync script and commit:

1. Run: `python scripts/sync_status.py`
2. Review the diff output
3. If anything changed, commit:
   ```bash
   git add PROJECT_BRIEF.md && git commit -m "docs: sync counters"
   ```

Do NOT manually edit counters in any file.
The sync script is the single source of truth for all project metrics.
