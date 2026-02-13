from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Robust import: works with `python -m scripts.validate_log_entry` AND `python scripts/validate_log_entry.py`
try:
    from backend.engine.schema_registry import SchemaRegistry, validate_instance
except ModuleNotFoundError:
    # Running as a file: sys.path[0] == ".../scripts", so add repo root
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from backend.engine.schema_registry import SchemaRegistry, validate_instance

def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _infer_schema_key(entry: Dict[str, Any], explicit: Optional[str]) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    sv = entry.get("schema_version")
    if isinstance(sv, str) and sv.strip():
        return sv.strip()
    return "session_log_entry.v1"

def validate_entry(entry: Dict[str, Any], schemas_dir: str = "backend/data/schemas", schema_key: Optional[str] = None) -> List[str]:
    reg = SchemaRegistry.from_dir(schemas_dir)
    key = _infer_schema_key(entry, schema_key)
    return validate_instance(entry, reg, key)

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Validate a session log entry against local JSON Schemas (with local $ref resolution)."
    )
    ap.add_argument("--schemas-dir", default="backend/data/schemas", help="Directory containing *.json schemas (default: data/schemas)")
    ap.add_argument("--schema", default=None, help="Schema key (e.g. session_log_entry.v1 or session_log_entry.v1.json). If omitted, uses entry.schema_version.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="Path to a single JSON entry file")
    g.add_argument("--json", help="Inline JSON string for a single entry")
    g.add_argument("--jsonl", help="Path to a JSONL file (validates each line)")
    ap.add_argument("--max-errors", type=int, default=20, help="Max errors to print (default: 20)")
    args = ap.parse_args()

    schemas_dir = args.schemas_dir

    def report_errors(prefix: str, errs: List[str]) -> None:
        print(f"{prefix}: INVALID ({len(errs)} errors)", file=sys.stderr)
        for e in errs[: args.max_errors]:
            print(f"- {e}", file=sys.stderr)
        if len(errs) > args.max_errors:
            print(f"... {len(errs) - args.max_errors} more", file=sys.stderr)

    if args.file:
        entry = _load_json(Path(args.file))
        errs = validate_entry(entry, schemas_dir=schemas_dir, schema_key=args.schema)
        if errs:
            report_errors(str(args.file), errs)
            return 2
        print("OK")
        return 0

    if args.json:
        entry = json.loads(args.json)
        if not isinstance(entry, dict):
            print("Inline JSON must be an object.", file=sys.stderr)
            return 2
        errs = validate_entry(entry, schemas_dir=schemas_dir, schema_key=args.schema)
        if errs:
            report_errors("<inline>", errs)
            return 2
        print("OK")
        return 0

    bad = 0
    total = 0
    p = Path(args.jsonl)
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        try:
            entry = json.loads(line)
        except Exception as e:
            bad += 1
            print(f"{p}:{i}: INVALID JSON ({e})", file=sys.stderr)
            continue
        if not isinstance(entry, dict):
            bad += 1
            print(f"{p}:{i}: INVALID (line is not an object)", file=sys.stderr)
            continue

        errs = validate_entry(entry, schemas_dir=schemas_dir, schema_key=args.schema)
        if errs:
            bad += 1
            report_errors(f"{p}:{i}", errs)

    if bad:
        print(f"SUMMARY: {bad}/{total} invalid", file=sys.stderr)
        return 2
    print(f"SUMMARY: {total} entries OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
