# D237 — Repo hygiene + memory consistency check

**Date:** 2026-05-11
**Last hygiene audit:** D156 (2026-03-25), ~149 briefs ago (warning emesso da `repo_hygiene.py`)
**Type:** D (read-only audit + light file moves)
**Predecessor in roadmap:** D156

---

## Phase 0 — Repo state

### `scripts/repo_hygiene.py` output

```
[OK] No completed brief docs found in docs/
[WARN] ROADMAP_CURRENT.md — 809 lines (target ≤350)
[WARN] Unexpected file at root: AUTH_AUDIT.md
[OK] No tracked .DS_Store
[OK] No large untracked files
[WARN] 149 briefs since last audit (2026-03-25) — consider running a full audit
=== Done. 3 warnings, 3 OK, 0 info ===
```

### Stale brief docs found

**`docs/briefs/`** (13 file pre-audit, di cui 10 archiviati in questo brief):

| File | Stato | Azione |
|---|---|---|
| `A-ACTIVATION-timing_parked.md` | brief A-ACTIVATION chiuso / parked | ✅ archiviato → `_archive/docs/briefs/` |
| `A-ACTIVATION-timing_phase0.md` | idem | ✅ archiviato |
| `A-ACTIVATION-timing_simulation.md` | idem | ✅ archiviato |
| `A-ACTIVATION-timing_subscription_audit.md` | idem | ✅ archiviato |
| `B208_proposal.md` | proposal Phase 0 di B208 (commit `fc2579e`), brief poi non cuttato | ✅ archiviato |
| `B214_B215_phase0_analysis.md` | B214/B215 chiusi | ✅ archiviato |
| `B216_phase1_analysis.md` | B216 chiuso | ✅ archiviato |
| `B217_session_duration_fix.md` | B217 chiuso | ✅ archiviato |
| `D214_phase0_analysis.md` | D214 chiuso | ✅ archiviato |
| `D214_source_taxonomy_normalization.md` | D214 chiuso | ✅ archiviato |
| `B202_proposal.md` | già tracciato per delete in D236 G1 F-29 | ⏸️ lasciato a D236 G1 |
| `B203_proposal.md` | idem F-29 | ⏸️ lasciato a D236 G1 |
| `B204_proposal.md` | idem F-29 | ⏸️ lasciato a D236 G1 |

**Top-level `docs/`** (4 file ricollocati in `docs/audit/`):

| File | Da | A |
|---|---|---|
| `A214_phase0_audit.md` | `docs/` | `docs/audit/` |
| `A215_phase0_audit.md` | `docs/` | `docs/audit/` |
| `A216_phase0_audit.md` | `docs/` | `docs/audit/` |
| `B183_duration_review.md` | `docs/` | `docs/audit/` |

### Temp / scratch files

```bash
find . -maxdepth 4 \( -name "*.tmp" -o -name "*.bak" -o -name "scratch*" -o -name "*~" \) \
  | grep -v node_modules | grep -v .venv | grep -v .next | grep -v .git
# → (empty)
```

✅ Nessuno.

### File a root non previsti

- `AUTH_AUDIT.md` — già tracciato in D236 Group 5 F-41 per move in `docs/audit/`. Non duplicato qui.

### `docs/audits/` (plurale)

3 file: `D-MEM-002_railway_memory_2026-05-07.md`, `D232_new_macrocycle_2026-05-05.md`, `D_guided_session_countdown_beep_2026-05-04.md`.
**Già tracciato per merge** in D236 Group 4 F-08. Non duplicato qui.

### `sync_status.py`

Bloccato perché `backend/data/user_state.json` è dirty (date di sviluppo locale: `last_assessed` 2026-05-04 → 2026-05-11). **Non è counter drift** — è la coppia di campi che `b15641a chore: refresh local user_state test fixture dates` periodicamente reset. Out of scope per questo audit.

---

## Phase 1 — Memory triangulation

### M1 — Body Part Picker pending fixes (A213) → 🟡 PARZIALE

**Memory claim:** *"Two small pending fixes in `body_part_picker.py`: copy `description` field to exercise instance + populate `suggested_external_load_kg`/`suggested_total_load_kg`."*

| Sotto-fix | Stato | Evidence |
|---|---|---|
| Populate `suggested_external_load_kg` / `suggested_total_load_kg` | ✅ **DONE** | `backend/engine/body_part_picker.py:601-603` (`apply_resolver_light`) — sets both keys quando `working_loads` ha entry per l'esercizio. |
| Copy `description` field to instance | ❌ **STILL MISSING** | `apply_resolver_light` (linee 558-572) costruisce `instance` dict senza copiare `exercise.get("description")`. Tutti i 218 esercizi in catalog hanno `description`, ma il dict instance non lo include. |

**Però**: nessun consumer frontend usa `exercise.description` nel rendering del path body-part picker:
- `frontend/src/components/training/session-card.tsx` (is_custom branch, lines 327-1236): **0 hit** su `.description` di exercise
- `frontend/src/components/training/exercise-detail-sheet.tsx`: **0 hit**
- Unico consumer: `frontend/src/components/circuit/CircuitTimer.tsx:588` — ma è Core Circuit, non body-part picker

**Conclusione:** cosmetic only. **Non bug, non blocker.** Raccomandazione: rimuovere la voce dalla memoria claude.ai (vedi Phase 3-F).

### M2 — Bundle B remediation status (B212, B213) → ✅ B212 DONE / ⚠️ B213 NON ESISTE

**Memory claim:** *"Bundle B remediation: B209 + B210 committed. Remaining: D211 (source taxonomy cross-module), B212 (axis dispatch), B213 (resolver pulling fallback)."*

| Brief | Stato | Evidence |
|---|---|---|
| D211 | ✅ closed by D214 | ROADMAP_CURRENT.md Priority 1.27 — F1/F3 chiusi da `assessment.tests_source` sidecar. |
| B212 | ✅ **DONE** | Commit `848eacd` "B212: guard checkout endpoint against overwriting active/trialing subscription". Archiviato in `docs/ROADMAP_v2.md:1143`. 4 nuovi test in `test_b212_checkout_guard.py`. |
| B213 | ⚠️ **GHOST — non esiste** | `git log --all \| grep -E '\bB21[2-3]\b'` ritorna solo B212 + un hash collision `b213e9c`. Zero riferimenti in `ROADMAP_CURRENT.md` o `ROADMAP_v2.md`. Probabilmente assorbito da B227 (resolver intensity_max enforcement 3-tier cascade, copre tematicamente "resolver pulling fallback") o mai cuttato. |

**Conclusione:** B212 chiuso pulito. B213 da rimuovere dalla memoria claude.ai. **Non aggiungere a roadmap** — il caso "pulling fallback" è coperto de facto da B227 e B224 (three-tier role cascade in body_part_picker).

### M3 — Free session core circuit expansion → 🟡 PARZIALE

**Memory claim:** *"D203 audit complete, difficulty reclassifications done, two toggles designed (easy/hard + pull-up bar). Confirmed additions from KB: Nordic curl, dragon flag tuck, star side plank, straddle L-sit, arch body hold, front lever tuck hold (bar), hanging leg raise (bar), hanging windshield wipers (bar). Still pending: final exercise list confirmation, C-type and A-type briefs."*

| Componente | Stato | Evidence |
|---|---|---|
| A-type brief (toggles) | ✅ **A203 merged** | `ca63ecb A203: core circuit easy/hard toggle + pull-up bar filter + 80/20 selection` |
| C-type brief (catalog) | ✅ **C205 merged** | `be0859d C205: core circuit catalog expansion — 10 new exercises + difficulty system` |
| Confirmed additions: `nordic_curl` | ✅ in catalog |
| Confirmed additions: `front_lever_tuck` | ✅ in catalog (commit `9a2e1c8 circuit: wire up front_lever_tuck + hanging_wipers images`) |
| Confirmed additions: `hanging_leg_raise` | ✅ in catalog |
| Confirmed additions: `hanging_windshield_wipers` (bar) | ~✅ presente come `windshield_wipers` (non con prefisso `hanging_`) |
| Confirmed additions: `dragon_flag` (tuck) | ❌ **MISSING** |
| Confirmed additions: `star_side_plank` | ❌ **MISSING** |
| Confirmed additions: `straddle_l_sit` | ❌ **MISSING** |
| Confirmed additions: `arch_body_hold` | ❌ **MISSING** |

Score: **4-5 di 8** confirmed additions in catalog. 4 mai aggiunti.

**Conclusione:** A e C briefs chiusi. La lista 8 della memoria era aspirazionale, non finale. Raccomandazione: rimuovere/revisionare la memoria; **eventualmente** un C-brief futuro per i 4 mancanti, ma solo se richiesti da UX (no automatic add).

---

## Phase 2 — Counter triangulation

| Metric | Live | PROJECT_BRIEF | Match |
|---|---|---|---|
| Tests | 1990 passed + **3 failed** = 1993 | 1993 | ⚠️ Total match, ma **3 fail** in `test_undo_session_B192.py` non riflessi |
| API endpoints | 66 router (`grep -E "^@router\." backend/api/routers/*.py \| wc -l`) + 2 app-level (`/health`, `/api/stripe/webhook`) = 68 | 68 | ✅ |
| Esercizi | 218 (`exercises.json` count) | 218 | ✅ |
| Sessioni | 35 | 35 | ✅ |
| Template | 19 | 19 | ✅ |

### Test failures (out-of-scope per fix, in-scope per report)

```
FAILED backend/tests/test_undo_session_B192.py::test_T2_end_to_end_undo_clears_ui_fields_across_fetches
FAILED backend/tests/test_undo_session_B192.py::test_T3_undo_preserves_feedback_log
FAILED backend/tests/test_undo_session_B192.py::test_T4_undo_preserves_working_loads_mutation
```

Tutti e tre falliscono per `AssertionError: no session in generated week plan` / `StopIteration` quando iterano `week_plan["weeks"][*].days[*].sessions`. Causa probabile: il fixture `user_state.json` ha `start_date=2026-05-11` (oggi) e `week_plans={}` vuoto al momento del test → `/api/week/0` ritorna struttura vuota. Storicamente esistono commit periodici `chore: refresh local user_state test fixture dates` (es. `b15641a`, `5e183ec`, `94a45b3`) per allinearli.

**Raccomandazione:** B-brief separato (suggerito **B249**) per fix-up — o (a) refresh delle date del fixture, o (b) seedare un week_plan prima del test, o (c) mockare `_get_or_generate_week`. Non in scope qui.

---

## Phase 3 — Actions taken

| # | Azione | Stato |
|---|---|---|
| A | Archiviati 10 brief docs da `docs/briefs/` → `_archive/docs/briefs/` | ✅ |
| A.1 | Lasciati `B202/B203/B204_proposal.md` in `docs/briefs/` (già scope D236 G1 F-29) | ⏸️ deferred |
| B | Ricollocati 4 audit deliverable da top-level `docs/` → `docs/audit/` | ✅ |
| C | `AUTH_AUDIT.md` root + `docs/audits/` dir merge | ⏸️ deferred a D236 G4/G5 |
| D | Scritto questo report `docs/audit/D237_repo_hygiene_2026-05-11.md` | ✅ |
| E | Aggiornato `ROADMAP_CURRENT.md` + `CLAUDE.md` ("Last full audit: D237 (2026-05-11)") | ✅ |
| F | Scritto memo claude.ai project memory (sezione sotto, da incollare manualmente) | ✅ |
| G | `sync_status.py` skipped — `user_state.json` dirty per ragioni unrelated | ⏸️ skipped |
| H | Fix 3 test B192 failing | ❌ out of scope (B-brief separato suggerito B249) |

### Memo per memoria claude.ai project (Daniele da incollare manualmente)

Tre voci da chiudere o revisionare:

> **M1 (Body Part Picker A213)** — Solo metà valida. `suggested_external_load_kg`/`suggested_total_load_kg` sono già populated in `apply_resolver_light` (commit fc255a7+). Il "copy `description` field" è ancora missing nel dict instance, **ma nessun consumer frontend lo legge** nel path body-part picker (verificato 2026-05-11, D237). → Rimuovere la voce dalla memoria o riformularla come "deferred until a frontend consumer needs it".
>
> **M2 (Bundle B B212 + B213)** — B212 chiuso (commit 848eacd, archiviato ROADMAP_v2.md). **B213 non è mai esistito**: zero hit in git e roadmap; probabilmente assorbito da B227 (resolver intensity_max cascade) o mai cuttato. → Rimuovere "B213 (resolver pulling fallback)" dalla memoria.
>
> **M3 (Free session core circuit)** — A203 toggles ✅ merged, C205 catalog +10 ✅ merged. Delle 8 confirmed additions: 4 in catalog (`nordic_curl`, `front_lever_tuck`, `hanging_leg_raise`, `windshield_wipers`), 4 mai aggiunti (`dragon_flag`, `star_side_plank`, `straddle_l_sit`, `arch_body_hold`). → Aggiornare la voce: "C-type/A-type briefs ✅ merged; lista 8 aspirational, 4 in catalog, 4 droppate/deferred".

---

## Recommendations for next briefs

1. **B249 (suggerito)** — Fix 3 test failures `test_undo_session_B192.py` (refresh fixture o seed week_plan).
2. **D236 Group 3** (già next-recommended in roadmap) — chiude counter drift CLAUDE.md/PROJECT_BRIEF (F-09/10/11/15/16).
3. **ROADMAP_CURRENT.md bloat** (809 righe vs target 350) — candidato per `python scripts/trim_roadmap.py` quando i completed superano i 20.
4. **Nessun action item engine** da questo audit.

---

## Files changed in D237

```
docs/audit/D237_repo_hygiene_2026-05-11.md  (new — this file)
docs/ROADMAP_CURRENT.md                      (D237 entry)
CLAUDE.md                                    (Last full audit date)
docs/briefs/* → _archive/docs/briefs/        (10 file moves)
docs/{A214,A215,A216}_phase0_audit.md → docs/audit/  (3 file moves)
docs/B183_duration_review.md → docs/audit/   (1 file move)
```
