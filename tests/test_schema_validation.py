import json
from pathlib import Path

from scripts.validate_log_entry import validate_entry

FIXT = Path(__file__).parent / "fixtures"

def load(name: str):
    return json.loads((FIXT / name).read_text(encoding="utf-8"))

def test_good_entry_passes():
    errs = validate_entry(load("log_good.json"))
    assert errs == []

def test_invalid_shallow_fails():
    errs = validate_entry(load("log_invalid_shallow.json"))
    assert len(errs) >= 1

def test_invalid_deep_fails_on_status_enum_or_type():
    errs = validate_entry(load("log_invalid_deep.json"))
    assert len(errs) >= 1
    # Should mention "status" somewhere
    assert any("status" in e for e in errs)
