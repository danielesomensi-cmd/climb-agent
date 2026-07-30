"""Re-run the 28-question coach regression set against the live coach.

Step 9 of A-COACH-KB-V1 was scored once by hand (D265 → 43/56). B310 (KB
router) and C263 (Base-floor alignment) changed what the model sees, so the
score had to be re-measured rather than re-interpreted. This script exists so
the re-run is repeatable after any KB or routing change instead of being a
one-off.

Questions are parsed out of `docs/coach/regression_scoring_v1.md` (single
source of truth — the rubric lives next to them). Each question runs in a
FRESH conversation so answers are standalone, exactly like the first pass.

Beyond the raw Q/A it records three machine checks that the human scorer
would otherwise do by eye:
  * routed L3 files (was the right knowledge even in context?)
  * engine-internal D-ID leaks (firewall, design.md §5)
  * cited "Author YYYY" sources absent from the KB (no-fabrication rule, §6)

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/coach_regression_rerun.py [--user <uuid>] [--out <path>]

Requires ALLOW_LEGACY_HEADER=1 and STORAGE_BACKEND=file (local dev only).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

SCORING_DOC = REPO_ROOT / "docs" / "coach" / "regression_scoring_v1.md"
DEFAULT_OUT = REPO_ROOT / "docs" / "coach" / "regression_rerun_raw.md"
DEFAULT_USER = "d2660000-0000-4000-a000-000000000266"

# design.md §5 — decisions that must never surface to the user.
FIREWALL_IDS = [
    "D03", "D04", "D05", "D06", "D08", "D13", "D23", "D32",
    "D42", "D61", "D62", "D63", "D88", "D90",
]

_QUESTION_RE = re.compile(r"^### (Q-\d+)[^\n]*\n\n\*\*Q:\*\* (.+)$", re.M)
# "Mujika 2012", "López-Rivera 2018", "Garrido-Palomino & España-Romero 2023"
_CITATION_RE = re.compile(r"\b([A-ZÀ-Ý][\wÀ-ÿ'’-]+(?:\s*&\s*[A-ZÀ-Ý][\wÀ-ÿ'’-]+)?)\s+(19|20)\d{2}\b")
# Words that look like a surname but are section noise.
_CITATION_STOPWORDS = {"Settimana", "Week", "Giorno", "Day", "Fase", "Phase", "Base"}


def parse_questions() -> list[tuple[str, str]]:
    text = SCORING_DOC.read_text(encoding="utf-8")
    return [(qid, q.strip()) for qid, q in _QUESTION_RE.findall(text)]


def kb_corpus() -> str:
    kb = REPO_ROOT / "backend" / "coach" / "knowledge"
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(kb.rglob("*.md"))
    )


def unknown_citations(reply: str, corpus: str) -> list[str]:
    """Cited sources whose surname does not appear anywhere in the KB."""
    found = []
    for surname, _ in _CITATION_RE.findall(reply):
        name = surname.strip()
        if name in _CITATION_STOPWORDS or name in found:
            continue
        if name.lower() not in corpus.lower():
            found.append(name)
    return found


def looks_truncated(reply: str) -> bool:
    """A reply cut mid-sentence — the Q-09/Q-16 failure mode of the first run."""
    tail = reply.rstrip()
    if not tail:
        return True
    return tail[-1] not in ".!?)`:*”\"'…" and not tail.endswith("|")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: export ANTHROPIC_API_KEY first")
        return 1

    from fastapi.testclient import TestClient

    from backend.api.main import app
    from backend.coach.routing import route_query
    from backend.engine import storage_file

    questions = parse_questions()
    if len(questions) != 28:
        print(f"WARNING: parsed {len(questions)} questions, expected 28")

    corpus = kb_corpus()
    client = TestClient(app)
    headers = {"X-User-ID": args.user}
    coach_log = Path(storage_file._coach_messages_path(args.user))

    model = os.environ.get("COACH_MODEL", "default (see llm_client)")
    lines = [
        "# Coach KB regression — re-run raw output",
        "",
        f"Generated {datetime.now().isoformat(timespec='seconds')} — model `{model}`, "
        f"user `{args.user}`, one fresh conversation per question.",
        "",
        "Machine checks per answer: routed L3 files, firewall D-ID leaks, "
        "cited sources absent from the KB, mid-sentence truncation.",
        "",
        "---",
        "",
    ]

    problems: list[str] = []
    for qid, question in questions:
        if coach_log.exists():
            coach_log.unlink()
        print(f"[{qid}] {question[:60]}…", flush=True)
        routed = [p.stem for p in route_query(question)]
        r = client.post("/api/coach/chat", json={"message": question}, headers=headers)
        reply = r.json()["reply"] if r.status_code == 200 else f"HTTP {r.status_code}: {r.text}"

        leaked = [d for d in FIREWALL_IDS if d in reply]
        unknown = unknown_citations(reply, corpus)
        truncated = looks_truncated(reply)
        if leaked:
            problems.append(f"{qid}: firewall leak {leaked}")
        if unknown:
            problems.append(f"{qid}: citations not in KB {unknown}")
        if truncated:
            problems.append(f"{qid}: truncated")

        lines += [
            f"## {qid}",
            "",
            f"**Q:** {question}",
            "",
            f"**Routed:** {', '.join(routed) or '(none)'}",
            f"**Firewall:** {'⚠️ ' + ', '.join(leaked) if leaked else 'clean'}  |  "
            f"**Citations not in KB:** {'⚠️ ' + ', '.join(unknown) if unknown else 'none'}  |  "
            f"**Truncated:** {'⚠️ yes' if truncated else 'no'}",
            "",
            "**A:**",
            "",
            reply,
            "",
            "---",
            "",
        ]

    if coach_log.exists():
        coach_log.unlink()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out}")
    print("\nMachine-check problems:" if problems else "\nMachine checks: all clean")
    for p in problems:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
