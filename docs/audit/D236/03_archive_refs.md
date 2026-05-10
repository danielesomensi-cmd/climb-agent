# D236 — Subagent C: _archive/ reverse references

Findings: P0=0, P1=1, P2=5, P3=0

Severity legend:
- P0 = CRITICAL: live code (backend/frontend/scripts/.py/.ts/.tsx) imports/opens/fetches an archived file
- P1 = REVIEW: live doc cites archived doc as authoritative
- P2 = mention only (informational, not load-bearing)
- P3 = false positive / no real reference

---

## Reference table

| archive_file | type | references_in_live_y_n | live_referrers (file:line) | severity | recommended_action |
|---|---|---|---|---|---|
| `_archive/docs/council/council_2026-04-01_11-45.md` | `.md` | Y | `docs/audit_docs_D197.md:76` | P2 | SAFE — mention in an audit table labelling the file as ARCHIVE, not a functional dependency |
| `_archive/docs/council/council_2026-04-01_16-30.md` | `.md` | Y | `docs/audit_docs_D197.md:77` | P2 | SAFE — mention in an audit table labelling the file as ARCHIVE, not a functional dependency |
| `_archive/docs/council/council_2026-04-02_test-peer-review.md` | `.md` | Y | `docs/audit_docs_D197.md:78` | P2 | SAFE — mention in an audit table labelling the file as ARCHIVE, not a functional dependency |
| `_archive/docs/council/council_2026-04-03_17-00.md` | `.md` | Y | `docs/audit_docs_D197.md:79` | P2 | SAFE — mention in an audit table labelling the file as ARCHIVE, not a functional dependency |
| `_archive/docs/council/council_2026-04-05_10-30.md` | `.md` | Y | `docs/audit_docs_D197.md:80` | P2 | SAFE — mention in an audit table labelling the file as ARCHIVE, not a functional dependency |
| `_archive/docs/frontend_audit_D163.md` | `.md` | Y | `docs/audit_docs_D197.md:28`, `docs/audit_docs_D197.md:133` | P2 | SAFE — both hits are in the D197 audit table recommending the file be moved to `_archive/`; no live system depends on its content |

---

## Anchor case: `_archive/docs/horst_integration_audit.md` — DANGLING REFERENCE

**The file does not exist anywhere in the repo** — not in `_archive/`, not in `docs/`, not tracked by git. It has been deleted (or never committed after being referenced), but `docs/ROADMAP_CURRENT.md` still cites it as authoritative at four locations:

| file:line | citation |
|-----------|----------|
| `docs/ROADMAP_CURRENT.md:244` | `> ... check _archive/docs/horst_integration_audit.md for enrichment material.` (standing rule for all deferred KB items) |
| `docs/ROADMAP_CURRENT.md:253` | `CUE-02 formalize` → `_archive/docs/horst_integration_audit.md §6` |
| `docs/ROADMAP_CURRENT.md:254` | `Coach KB spec: add 8 Hörst coaching cues` → `_archive/docs/horst_integration_audit.md §5` |
| `docs/ROADMAP_CURRENT.md:612` | D33 warm-up brief → `_archive/docs/horst_integration_audit.md §5-§6` |

Severity: **P1** — ROADMAP_CURRENT.md is a live, actively-read planning document. Any developer (or agent) following the ROADMAP instruction at line 244 will attempt to open a file that does not exist. The citations at lines 253, 254, and 612 point future implementors to a ghost source for authoritative KB content.

Note: `docs/audit_docs_D197.md:113` also mentions this file (`docs/horst_integration_audit.md → DELETE`) — but that line is in the D197 audit report itself, which was a read-only audit classifying what should be deleted. The D197 mention is P2-level (informational).

Recommended action: **UPDATE_LIVE_REFERENCE** — remove or replace the four citations in `docs/ROADMAP_CURRENT.md` with either (a) the actual location of the KB content if it exists in the "climb-agent knowledge base" claude.ai project, or (b) a note that the audit file was deleted and the KB content lives only in the external KB project memory. The standing rule at line 244 should either be removed or updated to omit the non-existent file path.

---

## Critical findings

No P0 findings. No live `.py`, `.ts`, `.tsx`, or executable script imports, opens, or fetches any file from `_archive/`.

---

## P1 finding detail

### ROADMAP_CURRENT.md cites a deleted file as authoritative knowledge source

`docs/ROADMAP_CURRENT.md` contains 4 citations to `_archive/docs/horst_integration_audit.md` (§5 and §6) as the canonical source for:
- CUE-02 coaching cue formalisation (forearm stretch rule)
- 8 Hörst coaching cues KB spec
- D33 warm-up function implementation guidance
- A standing rule for all deferred KB decisions (line 244)

The file does not exist. It was recommended for deletion in `docs/audit_docs_D197.md:113` with the rationale "Findings applied to engine, no active references" — however, at the time that audit was written, ROADMAP_CURRENT.md still referenced it, which means the audit's claim of "no active references" was incorrect.

Recommended unblock path: Find whether `horst_integration_audit.md` content was migrated to the external "climb-agent knowledge base" project (mentioned at ROADMAP line 240-241). If yes, update each citation to say the content lives in the KB project. If no, remove the four dangling citations from ROADMAP_CURRENT.md and note that the material is unavailable. Do not recreate the file from scratch — the audit and KB content it documented is external-project-dependent.

---

## Reverse-orphans

All 6 archived files under `_archive/` have no cross-references to each other within `_archive/`. Each file is independently orphaned from the live tree and from its archive siblings.

- `_archive/docs/council/council_2026-04-01_11-45.md` → no references from other archived files
- `_archive/docs/council/council_2026-04-01_16-30.md` → no references from other archived files
- `_archive/docs/council/council_2026-04-02_test-peer-review.md` → no references from other archived files
- `_archive/docs/council/council_2026-04-03_17-00.md` → no references from other archived files
- `_archive/docs/council/council_2026-04-05_10-30.md` → no references from other archived files
- `_archive/docs/frontend_audit_D163.md` → no references from other archived files

All 6 are candidates for deletion per the recommendation already recorded in `docs/audit_docs_D197.md`.

---

## Notes on scope

- Total files in `_archive/` inspected: **6** (all `.md`; no `.py`, `.json`, `.ts`, `.tsx`, or other types present)
- No live backend or frontend code references any `_archive/` path
- The `_archive` string appears in live `.py` and `.ts` files only as an unrelated variable name or string literal (macrocycle archival domain logic, test exclusion patterns) — these are confirmed false positives
- The D236 `00_inventory.md` file also contains many archive filenames — excluded because it is part of this same audit session and not a "live operational" reference
