Read-only audit of a single module. Argument: module path (e.g. `backend/engine/planner_v2.py`).

Analyze the module and report:

1. **Dead code** — unused functions, unreachable branches, commented-out blocks
2. **TODOs/FIXMEs** — list each with line number
3. **Missing test coverage** — public functions without corresponding test cases
4. **Vocabulary consistency** — check terms against `docs/vocabulary_v1.md`
5. **Import hygiene** — unused imports, circular risk
6. **Hardcoded values** — magic numbers or strings that should be constants

Output a structured report. Do NOT modify any files.
