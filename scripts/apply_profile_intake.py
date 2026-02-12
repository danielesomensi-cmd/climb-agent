from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]

VOCAB_LOCATIONS = {"home", "gym", "outdoor"}
VOCAB_EQUIPMENT = {
    "hangboard",
    "pullup_bar",
    "band",
    "weight",
    "dumbbell",
    "kettlebell",
    "pangullich",
    "spraywall",
    "board_kilter",
    "gym_boulder",
}
PROTECTED_TOP_LEVEL_KEYS = ("baselines", "tests", "history_index")


class IntakeError(ValueError):
    pass


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_schema(intake: Dict[str, Any]) -> None:
    schema_path = REPO_ROOT / "data" / "schemas" / "profile_intake.v1.json"
    schema = _read_json(schema_path)
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(intake), key=lambda err: list(err.absolute_path))
    if errors:
        messages: List[str] = []
        for err in errors:
            where = ".".join(str(x) for x in err.absolute_path) or "<root>"
            messages.append(f"{where}: {err.message}")
        raise IntakeError("Schema validation failed:\n- " + "\n- ".join(messages))


def _ensure_allowed_locations(values: Iterable[str], *, field: str) -> None:
    for value in values:
        if value not in VOCAB_LOCATIONS:
            raise IntakeError(f"Invalid location '{value}' in {field}. Allowed: {sorted(VOCAB_LOCATIONS)}")


def _ensure_allowed_equipment(values: Iterable[str], *, field: str) -> None:
    for value in values:
        if value not in VOCAB_EQUIPMENT:
            raise IntakeError(f"Invalid equipment '{value}' in {field}. Allowed: {sorted(VOCAB_EQUIPMENT)}")


def _validate_vocabulary(intake: Dict[str, Any]) -> None:
    equipment = (intake.get("equipment") or {}).get("gyms") or []
    for idx, gym in enumerate(equipment):
        _ensure_allowed_equipment(gym.get("equipment") or [], field=f"equipment.gyms[{idx}].equipment")

    defaults = intake.get("defaults") or {}
    if "location" in defaults:
        _ensure_allowed_locations([defaults["location"]], field="defaults.location")

    context = intake.get("context") or {}
    if "location" in context:
        _ensure_allowed_locations([context["location"]], field="context.location")

    availability = intake.get("availability") or {}
    for day, slots in availability.items():
        for slot, payload in (slots or {}).items():
            if "preferred_location" in payload:
                _ensure_allowed_locations([payload["preferred_location"]], field=f"availability.{day}.{slot}.preferred_location")
            if "locations" in payload:
                _ensure_allowed_locations(payload["locations"], field=f"availability.{day}.{slot}.locations")


def _normalize_gyms(gyms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for gym in gyms:
        normalized.append(
            {
                "gym_id": gym["gym_id"],
                "name": gym["name"],
                "equipment": sorted(set(gym.get("equipment") or [])),
            }
        )
    return sorted(normalized, key=lambda g: str(g.get("gym_id") or ""))


def _normalize_availability(availability: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for day in sorted(availability.keys()):
        day_slots = availability.get(day) or {}
        out_day: Dict[str, Any] = {}
        for slot in sorted(day_slots.keys()):
            payload = deepcopy(day_slots.get(slot) or {})
            if "locations" in payload:
                payload["locations"] = sorted(set(payload["locations"]))
            out_day[slot] = payload
        out[day] = out_day
    return out


def apply_profile_intake(intake: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    _validate_schema(intake)
    _validate_vocabulary(intake)

    updated = deepcopy(user_state)

    if "equipment" in intake and "gyms" in (intake.get("equipment") or {}):
        equipment = updated.setdefault("equipment", {})
        equipment["gyms"] = _normalize_gyms((intake.get("equipment") or {}).get("gyms") or [])

    if "availability" in intake:
        updated["availability"] = _normalize_availability(intake["availability"])

    if "planning_prefs" in intake:
        prefs = updated.setdefault("planning_prefs", {})
        prefs.update(deepcopy(intake["planning_prefs"]))

    if "defaults" in intake:
        defaults = updated.setdefault("defaults", {})
        defaults.update(deepcopy(intake["defaults"]))

    if "context" in intake:
        context = updated.setdefault("context", {})
        context.update(deepcopy(intake["context"]))

    for key in PROTECTED_TOP_LEVEL_KEYS:
        if key in user_state:
            updated[key] = deepcopy(user_state[key])

    return updated


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply profile_intake.v1 onto user_state deterministically")
    parser.add_argument("--in", dest="intake_path", required=True, help="Path to profile intake JSON")
    parser.add_argument("--user-state", required=True, help="Input user_state JSON path")
    parser.add_argument("--out", required=True, help="Output user_state JSON path")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    intake_path = Path(args.intake_path)
    user_state_path = Path(args.user_state)
    out_path = Path(args.out)

    intake = _read_json(intake_path)
    user_state = _read_json(user_state_path)
    merged = apply_profile_intake(intake, user_state)
    _write_json(out_path, merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
