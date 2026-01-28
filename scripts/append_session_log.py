import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def minimal_validate(entry: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    user = entry.get("user")
    if not isinstance(user, dict) or not str(user.get("id") or "").strip():
        errs.append("Missing or invalid user.id")

    outs = entry.get("exercise_outcomes")
    if not isinstance(outs, list) or len(outs) < 1:
        errs.append("exercise_outcomes must be a non-empty list")
        return errs

    for i, o in enumerate(outs):
        if not isinstance(o, dict):
            errs.append(f"exercise_outcomes[{i}] must be an object")
            continue
        if not str(o.get("exercise_id") or "").strip():
            errs.append(f"exercise_outcomes[{i}].exercise_id missing/empty")
        if "planned" not in o:
            errs.append(f"exercise_outcomes[{i}].planned missing")
        actual = o.get("actual")
        if actual is not None and not isinstance(actual, dict):
            errs.append(f"exercise_outcomes[{i}].actual must be an object if present")
        elif isinstance(actual, dict):
            st = actual.get("status", "planned")
            if st not in ("planned", "done", "skipped", "modified"):
                errs.append(f"exercise_outcomes[{i}].actual.status invalid: {st}")
    return errs


def normalize_v1(entry: Dict[str, Any]) -> Dict[str, Any]:
    # IMPORTANT: do NOT set schema_version here (no silent upgrade)
    entry.setdefault("logged_at", now_iso())

    outs = entry.get("exercise_outcomes")
    if isinstance(outs, list):
        for o in outs:
            if not isinstance(o, dict):
                continue
            actual = o.get("actual")
            if actual is None or not isinstance(actual, dict):
                actual = {}
            actual.setdefault("status", "planned")  # default
            o["actual"] = actual
    return entry


def get_bodyweight_kg(entry: Dict[str, Any], user_state_path: Optional[Path]) -> Optional[float]:
    # 1) Prefer explicit per-entry BW
    user = entry.get("user") or {}
    if isinstance(user, dict):
        bw = user.get("bodyweight_kg")
        if isinstance(bw, (int, float)):
            return float(bw)

    # 2) Fallback user_state.json (common patterns)
    if user_state_path and user_state_path.exists():
        try:
            us = read_json(user_state_path)
            bw2 = us.get("bodyweight_kg")
            if isinstance(bw2, (int, float)):
                return float(bw2)
            body = us.get("body") or {}
            if isinstance(body, dict):
                bw3 = body.get("bodyweight_kg")
                if isinstance(bw3, (int, float)):
                    return float(bw3)
        except Exception:
            pass
    return None


def autofill_used_total_load_kg(entry: Dict[str, Any], bw: Optional[float]) -> None:
    """
    Populate actual.used_total_load_kg if missing and BW is available.
    total = BW + used_added_weight_kg - used_assistance_kg
    Assistance is assumed positive kg of unloading.
    """
    if bw is None:
        return
    outs = entry.get("exercise_outcomes")
    if not isinstance(outs, list):
        return

    for o in outs:
        if not isinstance(o, dict):
            continue
        actual = o.get("actual")
        if not isinstance(actual, dict):
            continue

        if isinstance(actual.get("used_total_load_kg"), (int, float)):
            continue

        added = actual.get("used_added_weight_kg")
        assist = actual.get("used_assistance_kg")

        # legacy aliases
        if added is None:
            added = actual.get("added_weight_kg")
        if assist is None:
            assist = actual.get("assistance_kg")

        has_signal = (added is not None) or (assist is not None)
        if not has_signal:
            continue

        added_f = float(added) if isinstance(added, (int, float)) else 0.0
        assist_f = float(assist) if isinstance(assist, (int, float)) else 0.0
        total = bw + added_f - assist_f
        actual["used_total_load_kg"] = round(total, 2)
        o["actual"] = actual


def quarantine_invalid(entry: Dict[str, Any], errors: List[str], rejected_path: Path) -> None:
    payload = {"rejected_at": now_iso(), "reason": "invalid", "errors": errors, "entry": entry}
    append_jsonl(rejected_path, payload)


def quarantine_legacy(entry: Dict[str, Any], reason: str, legacy_path: Path) -> None:
    payload = {"quarantined_at": now_iso(), "reason": reason, "entry": entry}
    append_jsonl(legacy_path, payload)


def schema_validate_v1(entry: Dict[str, Any], schema_path: Path) -> List[str]:
    """
    Use the local schema registry validator (preferred).
    Falls back to jsonschema basic resolver if needed.
    """
    try:
        # robust import (works when running as file)
        try:
            from scripts.validate_log_entry import validate_entry as _validate_entry
        except ModuleNotFoundError:
            repo_root = Path(__file__).resolve().parents[1]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            from scripts.validate_log_entry import validate_entry as _validate_entry  # type: ignore

        schemas_dir = str(schema_path.resolve().parent)
        errs = _validate_entry(entry, schemas_dir=schemas_dir, schema_key=None)
        return errs
    except Exception as e:
        # fallback: keep old behavior
        try:
            import jsonschema  # type: ignore
        except Exception:
            return [f"jsonschema not available and validate_log_entry failed: {e}"]

        schema = read_json(schema_path)
        schema_path = schema_path.resolve()
        base_uri = schema_path.parent.as_uri() + "/"
        resolver = jsonschema.RefResolver(base_uri=base_uri, referrer=schema)  # type: ignore
        v = jsonschema.Draft7Validator(schema, resolver=resolver)

        errs: List[str] = []
        for err in sorted(v.iter_errors(entry), key=lambda er: list(er.path)):
            loc = ".".join([str(x) for x in err.path]) if err.path else "<root>"
            errs.append(f"{loc}: {err.message}")
        return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo_root", default=".")
    ap.add_argument("--log_template_path", required=True)
    ap.add_argument("--log_path", default="data/logs/sessions_2026.jsonl")
    ap.add_argument("--rejected_log_path", default="data/logs/session_logs_rejected.jsonl")
    ap.add_argument("--schema_path", default="data/schemas/session_log_entry.v1.json")
    ap.add_argument("--user_state_path", default="data/user_state.json")

    # Step-3 hardening: legacy routing
    ap.add_argument("--bak_dir", default="data/logs/_bak")
    ap.add_argument("--legacy_log_name", default="legacy_session_logs.jsonl")

    args = ap.parse_args()

    repo = Path(args.repo_root)
    entry = read_json(Path(args.log_template_path))

    # --- Hard gate: only v1 goes to main/rejected. Everything else is legacy.
    sv = entry.get("schema_version")
    if not isinstance(sv, str) or sv.strip() != "session_log_entry.v1":
        legacy_path = repo / args.bak_dir / args.legacy_log_name
        reason = "missing_schema_version" if not isinstance(sv, str) else f"schema_version_not_v1:{sv}"
        quarantine_legacy(entry, reason, legacy_path)
        print(f"Legacy log entry routed to: {legacy_path}", file=sys.stderr)
        return 3

    # V1 normalize + autofill
    entry = normalize_v1(entry)
    bw = get_bodyweight_kg(entry, repo / args.user_state_path)
    autofill_used_total_load_kg(entry, bw)

    # Validate
    errors: List[str] = []
    errors.extend(minimal_validate(entry))

    schema_abs = (repo / args.schema_path)  # works with absolute schema_path too
    errors.extend(schema_validate_v1(entry, schema_abs))

    if errors:
        quarantine_invalid(entry, errors, repo / args.rejected_log_path)
        print("Invalid log entry (quarantined).", file=sys.stderr)
        for e in errors[:50]:
            print(f"- {e}", file=sys.stderr)
        return 2

    append_jsonl(repo / args.log_path, entry)
    print(str(repo / args.log_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
