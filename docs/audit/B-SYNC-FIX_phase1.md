# B-SYNC-FIX — Phase 1 Analysis (read-only)

**Brief:** B-SYNC-FIX — Fix `sync_status.py` regex rotti + `validate()` rinforzato
**Phase:** 1 (Analysis, read-only) — output prima del STOP gate
**Generated:** 2026-05-10
**Inputs:** `scripts/sync_status.py`, `CLAUDE.md`, `docs/audit/D236/00_findings.md`, `docs/audit/D236/00_remediation_plan.md`
**Goal of this document:** present (1a) regex audit, (1b) validate strengthening pseudocode, (1c) sentinel test design, (1d) docstring draft. **Nothing implemented yet.**

---

## 1a — Regex audit

Tutti i pattern in `scripts/sync_status.py`. `target` indica dove il regex viene applicato. `status` è la classificazione: **ROTTO** (non matcha la realtà), **FRAGILE** (matcha oggi ma anchorato su free-prose con alto rischio di drift), **OK** (matcha pattern strutturale stabile), **DOCUMENTED LIMIT** (per design non auto-syncabile, → docstring 1d).

| line | function | pattern | target file:line | matches today? | status | proposed fix |
|------|----------|---------|------------------|----------------|--------|--------------|
| 46 | `count_tests` | `r".+\.py:\s*(\d+)$"` | pytest stdout (per-file lines) | yes | OK | — |
| 52 | `count_tests` fallback | `r"(\d+) test"` | pytest summary | yes | OK | — |
| 86 | `count_api_endpoints` | `r"\s*@router\.(get\|post\|put\|delete\|patch)\b"` | `backend/api/routers/*.py` source | yes (66 hits) | OK | — |
| 93 | `count_api_endpoints` | `r"\s*@app\.(get\|post\|put\|delete\|patch)\b"` | `backend/api/main.py` | yes (1 hit: health) | OK | — |
| 95 | `count_api_endpoints` | `r"\s*app\.add_api_route\b"` | `backend/api/main.py` | yes (1 hit: stripe webhook) | OK | — |
| 148 | `parse_old_counts` | `r"\|\s*(.+?)\s*\|\s*(\d+)\s*\|"` | STATUS_TABLE markdown | yes | OK (structural) | — |
| 169 | `update_marker_file` | `re.escape(START) + ".*?" + re.escape(END)` | content with markers | yes | OK | — |
| **200–202** | `update_claude` | **`r"\d+ endpoints total \(\d+ router \+ 1 app-level health check\)"`** | `CLAUDE.md:149` | **NO** (file says "2 app-level: health check + stripe webhook") | **ROTTO (F-01)** | pattern → `r"\d+ endpoints total \(\d+ router \+ 2 app-level: health check \+ stripe webhook\)"` ; replacement → `f"{endpoints} endpoints total ({endpoints - 2} router + 2 app-level: health check + stripe webhook)"` |
| 207–211 | `update_claude` | `r"# FastAPI REST API \(\d+ routers\)"` | `CLAUDE.md:113` | yes | FRAGILE (anchorato su tree comment) | KEEP — but covered by sentinel test |
| 214–218 | `update_claude` | `r"\*\*Pages \(\d+\):\*\*"` | `CLAUDE.md:222` | yes | FRAGILE (free-prose adjacent) | KEEP — but covered by sentinel test |
| 268 | `validate` | `r"^\| (GET\|POST\|PUT\|DELETE\|PATCH) "` (MULTILINE) | `CLAUDE.md` endpoint table | yes (64 rows found) | OK (structural) | — |
| 270 | `validate` | `r"(\d+) endpoints? total"` | `CLAUDE.md` endpoint header | yes (matches "64") | OK | — |

### Verifiche dirette eseguite

```
$ grep -n "endpoints total" CLAUDE.md
149:64 endpoints total (62 router + 2 app-level: health check + stripe webhook).

$ python -c "from sync_status import count_api_endpoints; print(count_api_endpoints())"
68

$ grep -c "^| \(GET\|POST\|PUT\|DELETE\|PATCH\) " CLAUDE.md
64
```

### Stato di drift attuale

| layer | dichiarato | reale | delta |
|-------|-----------|-------|-------|
| CLAUDE.md inline header (line 149) | 64 endpoints (62 router + 2 app-level) | 68 endpoints (66 router + 2 app-level) | +4 |
| CLAUDE.md endpoint table rows | 64 rows | 68 needed | -4 |
| `validate()` table-vs-header check | header 64 = table 64 → **no warning** | reality 68 ≠ docs 64 → invisible | silent |

Notare: la **coerenza interna** di CLAUDE.md (header=64, table=64) maschera il drift verso il codice reale. Questo è esattamente il gap che F-38 vuole chiudere.

### Sub-decisione (necessita conferma in STOP gate)

I 3 pattern di `update_claude()` sono oggi inline. Per permettere al sentinel test (1c) di importarli senza duplicazione, propongo di estrarli come costanti di modulo:

```python
# Top of sync_status.py, after constants
ENDPOINT_HEADER_REGEX = r"\d+ endpoints total \(\d+ router \+ 2 app-level: health check \+ stripe webhook\)"
ROUTER_HEADER_REGEX = r"# FastAPI REST API \(\d+ routers\)"
PAGES_HEADER_REGEX = r"\*\*Pages \(\d+\):\*\*"
ENDPOINT_TOTAL_PARSE_REGEX = r"(\d+) endpoints? total"
ENDPOINT_TABLE_ROW_REGEX = r"^\| (GET|POST|PUT|DELETE|PATCH) "
```

**Trade-off**:
- **A) Estrarre costanti** (raccomandato): test importa gli stessi pattern usati in produzione → impossibile drift test↔prod. Refactor minimo (~10 righe).
- **B) Test duplica i pattern** con commento "KEEP IN SYNC": zero refactor, ma il test può divergere silently → vale meno.

**Recommend A.** Decisione: confermare in STOP gate.

---

## 1b — `validate()` strengthening (pseudocode)

Stato attuale di `validate()` (lines 233–277):

| check | direzione | gap |
|-------|-----------|-----|
| disk → vocab (template files) | file esiste su disco ma non listato in vocab | non rileva il caso opposto |
| disk → vocab (session files) | id. | id. |
| header → table (CLAUDE.md, internal) | confronta header N vs righe tabella | non confronta vs `count_api_endpoints()` reale |

Gap: nessun check **vocab → disk** (F-37) e nessun check **CLAUDE.md ↔ codice reale** (F-38).

### Disegno dei nuovi check

```python
# ──────────────────────────────────────────────────────────────────────
# CHECK 1 — Reverse direction: vocab → disk (F-37)
# ──────────────────────────────────────────────────────────────────────
# Goal: catch the F-13 root cause (8 orphan template entries in vocab §3).
# Approach:
#   - Parse the canonical lists in vocabulary_v1.md
#   - For each id in the canonical list, verify a JSON file exists on disk
#   - Warn on entries with no file
#
# Parsing strategy:
#   - The vocabulary §3 has subsections "Module templates" and "Session
#     templates" with bulleted lists "- `<id>`".
#   - Two robust approaches considered:
#     (a) Section-aware parser: split on "##" headers, find the relevant
#         section, then grep "- `(\w+)`" inside.
#     (b) Naive whole-file grep "- `(\w+)`" + classify by checking which
#         disk catalog (templates vs sessions) the id appears in.
#   - Approach (a) is safer (no cross-section bleed). Use this.

def parse_vocab_canonical_list(vocab_content: str, kind: str) -> list[str]:
    """
    Extract canonical IDs for kind ∈ {"module", "session"} from vocab §3.
    Returns the list of ids declared in the canonical bulleted list.
    """
    # Heuristic: find the section header matching the kind
    header_pattern = (
        r"###?\s*[\d.]*\s*Canonical\s+" + kind + r"\s+template_ids"
        if kind in ("module", "session")
        else None
    )
    # Walk to the next "##"-level header, capture the slice in between,
    # then re.findall(r"-\s+`([a-zA-Z0-9_]+)`", slice)
    ...
    return ids  # list of strings, possibly empty

def check_vocab_to_disk(warnings: list[str]) -> None:
    if not os.path.exists(VOCAB_PATH):
        return
    with open(VOCAB_PATH) as f:
        vocab_content = f.read()

    disk_templates = set(os.path.splitext(os.path.basename(f))[0]
                         for f in glob.glob(
                             os.path.join(REPO_ROOT, "backend/catalog/templates/v1/*.json")))
    disk_sessions = set(os.path.splitext(os.path.basename(f))[0]
                        for f in glob.glob(
                             os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json")))

    for tid in parse_vocab_canonical_list(vocab_content, "module"):
        if tid not in disk_templates:
            warnings.append(
                f"vocabulary_v1.md: module template '{tid}' listed in canonical list "
                f"but no file at backend/catalog/templates/v1/{tid}.json")

    for sid in parse_vocab_canonical_list(vocab_content, "session"):
        if sid not in disk_sessions:
            warnings.append(
                f"vocabulary_v1.md: session template '{sid}' listed in canonical list "
                f"but no file at backend/catalog/sessions/v1/{sid}.json")

# Expected behavior on current repo:
#   - Should emit 8 warnings (the 8 orphans documented in F-13).


# ──────────────────────────────────────────────────────────────────────
# CHECK 2 — Code ↔ CLAUDE.md drift (F-38)
# ──────────────────────────────────────────────────────────────────────
# Goal: surface drift between count_api_endpoints() and the number declared
# in CLAUDE.md "N endpoints total". Two-phase: pre-update is diagnostic,
# post-update is a guardrail (= update_claude() failed if drift remains).

def parse_endpoint_header_total(claude_content: str) -> int | None:
    m = re.search(ENDPOINT_TOTAL_PARSE_REGEX, claude_content)
    return int(m.group(1)) if m else None

# Phase A — Pre-update (diagnostic, not a warning):
def diagnostic_pre_update(real_count: int) -> None:
    if not os.path.exists(CLAUDE_PATH):
        return
    with open(CLAUDE_PATH) as f:
        pre = f.read()
    pre_header = parse_endpoint_header_total(pre)
    if pre_header is None:
        print(f"  ℹ️  CLAUDE.md: cannot parse 'N endpoints total' header (regex broken?)")
    elif pre_header != real_count:
        print(f"  ℹ️  CLAUDE.md endpoint drift detected: "
              f"header={pre_header}, code={real_count} (will sync)")

# Phase B — Post-update (warning if regex didn't apply, F-38 guardrail):
def guardrail_post_update(real_count: int, warnings: list[str]) -> None:
    if not os.path.exists(CLAUDE_PATH):
        return
    with open(CLAUDE_PATH) as f:
        post = f.read()
    post_header = parse_endpoint_header_total(post)
    if post_header is None:
        warnings.append(
            "CLAUDE.md: cannot parse endpoint header line. "
            "update_claude() regex may not match current text. "
            "See sync_status.py:200 (ENDPOINT_HEADER_REGEX).")
    elif post_header != real_count:
        warnings.append(
            f"POST-SYNC DRIFT: CLAUDE.md endpoint header is {post_header} "
            f"but code has {real_count} endpoints. "
            f"update_claude() did not apply the fix — likely a broken regex. "
            f"See sync_status.py:200 (ENDPOINT_HEADER_REGEX).")
```

### Integration in `main()`

Sequence:
```
check_uncommitted_work()
counts = collect_counts()
real_endpoints = dict(counts)["API endpoints"]

# print counts...

print("Pre-sync diagnostics...")
diagnostic_pre_update(real_endpoints)        # NEW (F-38 phase A)

print("Syncing files...")
update_marker_file(BRIEF_PATH, ...)
update_marker_file(README_PATH, ...)
update_claude(real_endpoints, routers, pages)

warnings = validate(real_endpoints)
guardrail_post_update(real_endpoints, warnings)  # NEW (F-38 phase B)
check_vocab_to_disk(warnings)                    # NEW (F-37)
# print warnings...
```

Why split pre/post:
- **Pre** is diagnostic (`ℹ️`): expected on every run that fixes drift. NOT a warning.
- **Post** is a guardrail (`⚠️`): means the auto-fix didn't land. Loud signal.

This avoids flooding warnings on benign drift-and-fix cycles while still alerting on regex-broken silent failures.

---

## 1c — Sentinel test design

**Path:** `backend/tests/test_sync_status_sentinel.py`
**Snapshot fixtures:** `backend/tests/fixtures/sync_snapshots/`
**Approach:** snapshot of CLAUDE.md / PROJECT_BRIEF.md / README.md captured at fix time. Tests assert that every pattern in `sync_status.py` matches its target snapshot. **Tests structure, not values.**

### Fixture lifecycle

| event | action |
|-------|--------|
| Initial creation (during B-SYNC-FIX Phase 2) | `cp CLAUDE.md backend/tests/fixtures/sync_snapshots/CLAUDE.md.snapshot` (and analogues) |
| Doc text intentionally restructured (e.g., "endpoints total" phrasing changes) | Update both `sync_status.py` regex AND the snapshot in same commit |
| Counter changes (e.g., 64 → 68) | **Do not update fixture.** The test asserts pattern match, not value. |
| New regex added to `sync_status.py` | Add a new `def test_<name>_pattern_matches_snapshot()` test |

### Test file (skeleton)

```python
"""
Sentinel tests for scripts/sync_status.py regex patterns.

If these fail, sync_status.py has stopped matching the documented sentence
structure of CLAUDE.md / PROJECT_BRIEF.md / README.md. See B-SYNC-FIX.

The fixtures live in backend/tests/fixtures/sync_snapshots/ and are snapshots
of the docs at the time B-SYNC-FIX shipped. Update them ONLY when the sentence
structure in the live docs intentionally changes — never to chase counter drift.
The sentinel guards structure, not values.
"""
import re
from pathlib import Path

import pytest

# Import patterns from sync_status (assumes 1a sub-decision A: extract as constants)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from sync_status import (  # type: ignore
    ENDPOINT_HEADER_REGEX,
    ROUTER_HEADER_REGEX,
    PAGES_HEADER_REGEX,
    ENDPOINT_TOTAL_PARSE_REGEX,
    ENDPOINT_TABLE_ROW_REGEX,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sync_snapshots"


@pytest.fixture(scope="module")
def claude_snapshot() -> str:
    return (FIXTURE_DIR / "CLAUDE.md.snapshot").read_text()


@pytest.fixture(scope="module")
def brief_snapshot() -> str:
    return (FIXTURE_DIR / "PROJECT_BRIEF.md.snapshot").read_text()


@pytest.fixture(scope="module")
def readme_snapshot() -> str:
    return (FIXTURE_DIR / "README.md.snapshot").read_text()


def test_endpoint_header_regex_matches_claude(claude_snapshot):
    assert re.search(ENDPOINT_HEADER_REGEX, claude_snapshot), (
        "ENDPOINT_HEADER_REGEX no longer matches CLAUDE.md. "
        "If the endpoint header sentence was restructured, update both the "
        "regex in sync_status.py and the fixture. See B-SYNC-FIX.")


def test_router_header_regex_matches_claude(claude_snapshot):
    assert re.search(ROUTER_HEADER_REGEX, claude_snapshot), (
        "ROUTER_HEADER_REGEX no longer matches CLAUDE.md. See B-SYNC-FIX.")


def test_pages_header_regex_matches_claude(claude_snapshot):
    assert re.search(PAGES_HEADER_REGEX, claude_snapshot), (
        "PAGES_HEADER_REGEX no longer matches CLAUDE.md. See B-SYNC-FIX.")


def test_endpoint_total_parse_regex_matches_claude(claude_snapshot):
    assert re.search(ENDPOINT_TOTAL_PARSE_REGEX, claude_snapshot), (
        "ENDPOINT_TOTAL_PARSE_REGEX no longer matches CLAUDE.md. See B-SYNC-FIX.")


def test_endpoint_table_row_regex_matches_claude(claude_snapshot):
    rows = re.findall(ENDPOINT_TABLE_ROW_REGEX, claude_snapshot, re.MULTILINE)
    assert len(rows) > 0, (
        "ENDPOINT_TABLE_ROW_REGEX found zero rows in CLAUDE.md. See B-SYNC-FIX.")


def test_status_table_markers_present_brief(brief_snapshot):
    assert "<!-- STATUS_TABLE_START -->" in brief_snapshot
    assert "<!-- STATUS_TABLE_END -->" in brief_snapshot


def test_status_table_markers_present_readme(readme_snapshot):
    assert "<!-- STATUS_TABLE_START -->" in readme_snapshot
    assert "<!-- STATUS_TABLE_END -->" in readme_snapshot
```

### Negative test (Phase 3 manual sanity)

Da eseguire una sola volta in Phase 3, **non committare la rottura**:

```bash
# Temporarily corrupt one regex to confirm the sentinel actually fails
python -c "
content = open('scripts/sync_status.py').read()
broken = content.replace('ENDPOINT_HEADER_REGEX = r\"', 'ENDPOINT_HEADER_REGEX = r\"XXXXX')
open('scripts/sync_status.py', 'w').write(broken)
"
python -m pytest backend/tests/test_sync_status_sentinel.py -q   # MUST FAIL
git checkout scripts/sync_status.py                              # restore
```

---

## 1d — Module docstring (sync limits)

Da inserire come blocco docstring in cima a `scripts/sync_status.py`, sostituendo l'attuale docstring (lines 1–16):

```python
#!/usr/bin/env python3
"""Sync real project counters into PROJECT_BRIEF.md, CLAUDE.md, and README.md.

Usage:
    python scripts/sync_status.py

Reads counts from the codebase and updates:
  - PROJECT_BRIEF.md  (status table between markers)
  - README.md         (status table between markers)
  - CLAUDE.md         (endpoint total + router count + page count, inline)

Also runs validation checks and prints warnings for issues that cannot be
auto-fixed (e.g., missing template IDs in vocabulary, vocab→disk orphans,
CLAUDE.md endpoint header drift vs code).

No external dependencies — stdlib only (+ pytest subprocess).

## Sync limits — won't auto-update

The following content is INTENTIONALLY not auto-synced. Edit by hand as part
of the brief that introduces the change.

- Tech-stack tables (PROJECT_BRIEF.md tech stack section, ~lines 71-78)
- Pricing rows (ROADMAP_CURRENT.md Priority 4 / Future)
- GTM Sprint status callouts (ROADMAP_CURRENT.md Priority 1.75, ~lines 85-89)
- The CLAUDE.md endpoint TABLE rows (only the inline header gets auto-updated;
  the table rows must be edited manually when adding/removing endpoints)
- Any free-prose status assertion ("LIVE since YYYY-MM-DD", "TEST MODE",
  "temporarily disabled", etc.) anywhere in the doc tree

If a counter / status / table changes, update it in the same brief that
introduces the change. The sentinel test in
`backend/tests/test_sync_status_sentinel.py` guards the regex patterns'
structural match against snapshot fixtures of the source docs.
"""
```

E aggiungere a `CLAUDE.md` §"Docs maintenance", come bullet aggiuntivo:

```markdown
- The auto-sync script does NOT touch tech-stack tables, pricing rows, status
  callouts, or the CLAUDE.md endpoint table rows. See the docstring of
  `scripts/sync_status.py` for the full list of auto-sync limits.
```

---

## Summary — what Phase 2 will implement

| step | file | change |
|------|------|--------|
| 1 | `scripts/sync_status.py:200-204` | Fix regex+replacement F-01 |
| 2 | `scripts/sync_status.py` (top, before constants) | Extract `ENDPOINT_HEADER_REGEX`, `ROUTER_HEADER_REGEX`, `PAGES_HEADER_REGEX`, `ENDPOINT_TOTAL_PARSE_REGEX`, `ENDPOINT_TABLE_ROW_REGEX` as module constants (sub-decision A) |
| 3 | `scripts/sync_status.py` validate() + main() | Add `check_vocab_to_disk()` (F-37), `diagnostic_pre_update()` + `guardrail_post_update()` (F-38), wire into main() |
| 4 | `scripts/sync_status.py` (top docstring) | Replace docstring with sync-limits version (1d, F-39 + F-40) |
| 5 | `CLAUDE.md` §"Docs maintenance" | Add 1-bullet pointer to docstring |
| 6 | `backend/tests/fixtures/sync_snapshots/{CLAUDE,PROJECT_BRIEF,README}.md.snapshot` | Create as `cp` of live files at fix time |
| 7 | `backend/tests/test_sync_status_sentinel.py` | Create with 7 sentinel tests (1c) |

**Side-effect of running `python scripts/sync_status.py` after Phase 2** (expected):
- CLAUDE.md inline endpoint header transitions `64 → 68` (F-01 unblocked)
- 8 vocab→disk orphan warnings emitted (F-37 active)
- No `POST-SYNC DRIFT` warning (F-38 confirms regex applied)
- Idempotent on subsequent runs

**Acceptance criteria** (mirror brief, expanded):
- [ ] All ROTTO patterns in 1a → fixed
- [ ] All FRAGILE patterns in 1a → covered by sentinel test
- [ ] All DOCUMENTED LIMIT items in 1d → listed in docstring
- [ ] `validate()` emits warning on at least one of the 8 vocab orphan entries
- [ ] `validate()` post-update does NOT emit POST-SYNC DRIFT after a clean run
- [ ] Sentinel test passes
- [ ] Negative sentinel test (manually break regex) confirms test fails loudly
- [ ] Test suite total increments by 7 (sentinel tests added)
- [ ] CLAUDE.md §"Docs maintenance" contains pointer bullet

---

## Open questions for Daniele (STOP gate)

1. **Sub-decision A (regex constants extraction)** — confirmare? Senza estrazione, il sentinel test deve duplicare i pattern e tenerli in sync a mano. Con estrazione, refactor minimo (~10 linee) ma sentinel test importa direttamente.

2. **Scope di `parse_vocab_canonical_list()`** — il vocab ha sottosezioni "Canonical module template_ids" (§3) e "Canonical session template_ids" (§3 dopo). La parsing strategy proposta richiede 1 regex per identificare la sezione + 1 per estrarre gli id. Va bene complessità, o vuoi un approccio più semplice (e.g., assumere che ogni line `- \`name\`` *prima della prossima `##` header* faccia parte della lista corrente)?

3. **Negative sentinel test** in Phase 3 — eseguito a mano (rompo regex temporaneamente, verifico che il test fallisca, restore). NON automatizzato, NON committato. Confermi questa procedura?

4. **F-39 (auto-update tabella endpoint CLAUDE.md)** — confermo: documentato come limite, NON implementato in questo brief. Eventuale follow-up A-SYNC-ENDPOINT-TABLE separato.

5. **`docs/audit/B-SYNC-FIX_phase1.md`** (questo file) — committarlo nello stesso commit della Phase 2 o in un commit separato Phase-1-only? Brief lascia flessibilità ("stampato a console / committato come"). Default mio: un solo commit per tutto il brief al termine.
