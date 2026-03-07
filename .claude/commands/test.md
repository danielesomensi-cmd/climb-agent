Run the full test suite:
```bash
source .venv/bin/activate && python3 -m pytest backend/tests/ -q 2>&1 | tail -5
```

- If all tests **pass**: report the total count.
- If any tests **fail**: show the full failure output and fix them before doing anything else.
