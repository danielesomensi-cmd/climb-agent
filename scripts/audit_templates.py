#!/usr/bin/env python3
"""Audit script: prints a markdown table of all session templates and module templates."""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DIRS = {
    "sessions": REPO_ROOT / "backend" / "catalog" / "sessions" / "v1",
    "templates": REPO_ROOT / "backend" / "catalog" / "templates" / "v1",
}


def extract_nested(data: dict, *keys, default="—"):
    """Walk nested keys, return value or default."""
    cur = data
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return default
    return cur if cur is not None else default


def load_sessions(directory: Path) -> list[dict]:
    rows = []
    for f in sorted(directory.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)

        template_id = f.stem
        training_focus = extract_nested(data, "intent", "primary_goal")
        location = extract_nested(data, "context", "location")
        # Some files have location at top level
        if location == "—":
            location = data.get("location", "—")
        description = data.get("description", "—")

        # Extract module names (template_id or block_id)
        modules = []
        for m in data.get("modules", []):
            mid = m.get("template_id") or m.get("block_id") or "?"
            modules.append(mid)

        rows.append({
            "source": "session",
            "template_id": template_id,
            "training_focus": training_focus,
            "location": location,
            "description": description,
            "modules": modules,
        })
    return rows


def load_templates(directory: Path) -> list[dict]:
    rows = []
    for f in sorted(directory.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)

        template_id = f.stem
        training_focus = data.get("category", "—")

        # Location from required_environment
        env = data.get("required_environment", {})
        loc_list = env.get("any_of") or env.get("all_of") or []
        location = ", ".join(loc_list) if loc_list else "—"

        description = data.get("description", "—")

        # Blocks instead of modules
        blocks = []
        for b in data.get("blocks", []):
            bid = b.get("block_id") or b.get("type") or "?"
            blocks.append(bid)

        rows.append({
            "source": "template",
            "template_id": template_id,
            "training_focus": training_focus,
            "location": location,
            "description": description,
            "modules": blocks,
        })
    return rows


def truncate(s: str, maxlen: int = 60) -> str:
    if len(s) <= maxlen:
        return s
    return s[: maxlen - 1] + "…"


def print_table(title: str, rows: list[dict]):
    print(f"\n## {title}\n")
    print(f"| template_id | training_focus | location | modules | description |")
    print(f"|-------------|----------------|----------|---------|-------------|")
    for r in rows:
        mods = ", ".join(r["modules"]) if r["modules"] else "—"
        desc = truncate(str(r["description"]))
        print(f"| {r['template_id']} | {r['training_focus']} | {r['location']} | {mods} | {desc} |")
    print(f"\n**Total: {len(rows)}**")


def main():
    for label, dirpath in DIRS.items():
        if not dirpath.exists():
            print(f"\n## {label} — directory not found: {dirpath}")
            continue

        if label == "sessions":
            rows = load_sessions(dirpath)
        else:
            rows = load_templates(dirpath)

        print_table(label, rows)


if __name__ == "__main__":
    main()
