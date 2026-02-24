import json
from pathlib import Path

from backend.engine.validate_log_entry import validate_entry

FIXT = Path(__file__).parent / "fixtures"
SCHEMAS_DIR = str(Path(__file__).resolve().parents[2] / "backend" / "data" / "schemas")

def load(name: str):
    return json.loads((FIXT / name).read_text(encoding="utf-8"))

def test_good_entry_passes():
    errs = validate_entry(load("log_good.json"), schemas_dir=SCHEMAS_DIR)
    assert errs == []

def test_invalid_shallow_fails():
    errs = validate_entry(load("log_invalid_shallow.json"), schemas_dir=SCHEMAS_DIR)
    assert len(errs) >= 1

def test_invalid_deep_fails_on_status_enum_or_type():
    errs = validate_entry(load("log_invalid_deep.json"), schemas_dir=SCHEMAS_DIR)
    assert len(errs) >= 1
    # Should mention "status" somewhere
    assert any("status" in e for e in errs)
