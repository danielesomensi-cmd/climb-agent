from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def norm_str(value: Any) -> str:
    return str(value).strip().lower()


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def norm_list_str(value: Any) -> List[str]:
    return [norm_str(v) for v in as_list(value) if norm_str(v)]


def sorted_join(value: Any) -> str:
    items = sorted(norm_list_str(value))
    return "+".join(items)


def cluster_key_for_exercise(exercise: Dict[str, Any]) -> str:
    domain = sorted_join(exercise.get("domain"))
    role = sorted_join(exercise.get("role") or exercise.get("roles"))
    equipment = sorted_join(exercise.get("equipment_required"))
    pattern_value = exercise.get("pattern") if "pattern" in exercise else exercise.get("movement")
    pattern = sorted_join(pattern_value)
    return f"domain={domain}|role={role}|eq={equipment}|pattern={pattern}"


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
