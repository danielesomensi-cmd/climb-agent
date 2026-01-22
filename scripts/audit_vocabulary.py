import json
import re
import sys
from pathlib import Path

VOCAB_PATH = Path("docs/vocabulary_v1.md")

def extract_section_values(md: str, heading_regex: str):
    m = re.search(heading_regex, md, flags=re.I | re.S)
    if not m:
        return set()
    block = m.group(1)
    # values are typically written as: - `value`
    return set(re.findall(r"-\s+`([^`]+)`", block))

def load_vocab():
    md = VOCAB_PATH.read_text(encoding="utf-8")

    # Grab blocks between headings and the next '---' or next '###'
    def block_after(title: str):
        # capture lazily until next ### or --- delimiter
        pat = rf"(?:^|\n)###\s+{re.escape(title)}.*?\n(.*?)(?:\n---\s*|\n###\s+|\Z)"
        return extract_section_values(md, pat)

    # These headings must match your vocabulary file titles
    allowed = {
        "equipment": block_after("1.2 Equipment (canonical IDs)"),
        "domain": block_after("2.2 Domain (capacity / training goal)"),
        "pattern": block_after("2.4 Pattern (movement / protocol shape)"),
        "role": block_after("2.3 Role (phase of session)") or block_after("Role (phase of session)"),
    }

    # If role section is not present in md, we keep it permissive but warn.
    if not allowed["role"]:
        print("WARNING: role section not found in docs/vocabulary_v1.md (role checks will be skipped).", file=sys.stderr)

    return allowed

def iter_json_files(root: Path):
    for p in root.rglob("*.json"):
        yield p

def norm_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def check_exercises(allowed):
    ex_path = Path("catalog/exercises/v1/exercises.json")
    ex = json.loads(ex_path.read_text(encoding="utf-8"))
    items = ex.get("exercises") or ex.get("items") or ex
    if not isinstance(items, list):
        raise SystemExit("Unexpected exercises.json structure")

    bad = []
    for e in items:
        ex_id = e.get("id")
        # equipment
        for eq in norm_list(e.get("equipment") or e.get("equipment_required")):
            if allowed["equipment"] and eq not in allowed["equipment"]:
                bad.append(("exercise_equipment", ex_id, eq))
        # domain (string or list)
        for d in norm_list(e.get("domain")):
            if allowed["domain"] and d not in allowed["domain"]:
                bad.append(("exercise_domain", ex_id, d))
        # pattern
        for p in norm_list(e.get("pattern")):
            if allowed["pattern"] and p not in allowed["pattern"]:
                bad.append(("exercise_pattern", ex_id, p))
        # role
        if allowed["role"]:
            for r in norm_list(e.get("role")):
                if r not in allowed["role"]:
                    bad.append(("exercise_role", ex_id, r))
    return bad

def check_templates_and_sessions(allowed):
    roots = [Path("catalog/templates"), Path("catalog/sessions")]
    bad = []
    for root in roots:
        if not root.exists():
            continue
        for p in iter_json_files(root):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                bad.append(("json_parse", str(p), str(e)))
                continue

            # scan recursively for keys we care about
            def walk(node):
                if isinstance(node, dict):
                    for k, v in node.items():
                        if k in ("equipment_required", "equipment"):
                            for eq in norm_list(v):
                                if allowed["equipment"] and eq not in allowed["equipment"]:
                                    bad.append(("template_equipment", str(p), eq))
                        if k == "domain":
                            for d in norm_list(v):
                                if allowed["domain"] and d not in allowed["domain"]:
                                    bad.append(("template_domain", str(p), d))
                        if k == "pattern":
                            for pat in norm_list(v):
                                if allowed["pattern"] and pat not in allowed["pattern"]:
                                    bad.append(("template_pattern", str(p), pat))
                        if k == "role" and allowed["role"]:
                            for r in norm_list(v):
                                if r not in allowed["role"]:
                                    bad.append(("template_role", str(p), r))
                        walk(v)
                elif isinstance(node, list):
                    for it in node:
                        walk(it)

            walk(obj)
    return bad

def main():
    allowed = load_vocab()

    bad = []
    bad += check_exercises(allowed)
    bad += check_templates_and_sessions(allowed)

    if bad:
        print("\n=== VOCABULARY COHERENCE ERRORS ===")
        for kind, where, val in bad:
            print(f"- {kind}: {where} -> {val}")
        print("\nFix the vocabulary or the offending values. Failing audit.")
        sys.exit(2)

    print("OK: vocabulary coherence audit passed.")

if __name__ == "__main__":
    main()
