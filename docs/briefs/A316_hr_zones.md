# A316 — FC massima e fasce cardio in bpm

**Tipo:** A (feature) · **Moduli ad alto rischio toccati:** `resolve_session.py` (solo pass-through di un campo), schema `user_state` (`body.*`) · **Fase 1 approvata da Daniele il 2026-10-16** → si riparte dalla fase 2 (completare l'implementazione).
**Branch/worktree:** `brief/A316-hr-zones` in `../climb-agent-a316` (creato con `scripts/start_brief.py` da origin/main). Il brief tocca `frontend/` → **branch + preview Vercel + OK di Daniele prima del merge**.

## Perché

L'app non conosce la frequenza cardiaca: gli esercizi cardio dicono solo «60-70% of max heart rate» e il cue del cammino in salita suggerisce la formula 208 − 0,7 × età, che per Daniele sbaglia di ~10 bpm (FCmax misurata ≥ 190, formula 180). Il 4x4 del catalogo diceva anche «85-95%, recupero camminando», in contrasto con Helgerud 2007 (90-95%, recupero di corsetta ~70%).

## Design (approvato)

1. **Stato** — tre campi facoltativi in `body` (già in `_ALLOWED_STATE_KEYS`, nessun cambio API):
   `hr_max_bpm` (int 120-230), `hr_rest_bpm` (int 30-110), `hr_max_source` (`"measured"` | `"estimated"`).
   Settings scrive in `assessment.body` e lo specchia in `body` (flusso B270 già esistente). Lettura: `body` prima, poi `assessment.body`. Valori fuori range = assenti.
2. **Catalogo** — campo strutturato `hr_target` su 5 esercizi:
   `easy_run_zone2`, `treadmill_incline_walk`, `stationary_bike_zone2`, `approach_hike_loaded` → `{"basis":"hr_max","work_pct":[60,70]}`;
   `treadmill_hiit_4x4` → `{"basis":"hr_max","work_pct":[90,95],"recovery_pct":[65,75]}`.
   Testo del 4x4 corretto (90-95%, recupero «easy jog at about 70%», Helgerud 2007); cue del cammino senza formula d'età.
3. **Motore** — `hr_target` copiato così com'è nell'istanza risolta (2 punti in `resolve_session.py`, solo se presente: le istanze senza banda non cambiano forma). Nessun calcolo nel motore, nessun effetto su selezione, piano, progressione, closed loop.
4. **Custom** — `hr_target` derivato dal catalogo **in lettura** (come `alt_sides`): `enrich_custom_sessions_for_play` e `_with_custom_anchored_loads` in `week.py` (solo sessioni non giocate; done/skipped restituite come salvate, piano salvato intatto).
5. **Frontend** — bpm calcolati **solo a video** (`src/lib/hr-zones.ts`, specchio di `backend/engine/hr_zones.py`). Nel player guidato, sotto la prescrizione: «♥ Work 171-180 bpm · Recovery 124-142 bpm». Senza FCmax: percentuali + «Set your max heart rate in Settings». **Nessuna stima da età.**
6. **Settings** — due campi nel dialog profilo (Max heart rate, Resting heart rate) con validazione; riga «Max heart rate» nella card profilo. Salvare la FCmax imposta `hr_max_source: "measured"`.
7. **Coach** — `prompt_builder._profile_section` aggiunge una riga (`hr_zones.coach_line`) con FCmax e fasce in bpm, solo se la FCmax è registrata.

Fuori scope: aggiornamento automatico della FCmax da Garmin (`~/Projects/garmin-ingest`), scheda esercizio pre-play (`exercise-detail-sheet.tsx`) — vedi sotto.

## Stato al 2026-10-17 00:10 (worktree, NON committato)

Fatto:
- `backend/engine/hr_zones.py` (nuovo): `hr_max`, `hr_rest`, `bpm_band`, `coach_line`.
- `backend/catalog/exercises/v1/exercises.json`: `hr_target` sui 5 esercizi + testi 4x4 / incline walk.
- `backend/engine/resolve_session.py`: pass-through nei 2 punti (`_resolve_inline_block` e loop principale). Prehab non toccato (nessun cardio).
- `backend/api/routers/custom_session.py`, `backend/api/routers/week.py`: backfill in lettura.
- `backend/coach/prompt_builder.py`: riga FC.
- `backend/tests/test_a316_hr_zones.py`: 8 test, **verdi**.
- Frontend: `src/lib/hr-zones.ts` + `src/lib/__tests__/hr-zones.test.ts`, `types.ts` (`GuidedExercise.hrTarget`), `session-card.tsx` e `guided-session-utils.ts` (mappano `hr_target`), `guided-exercise-step.tsx` (prop `hrMax`, riga ♥), pagina guided (`useUserState` abilitato solo se una riga ha `hrTarget`), `settings/page.tsx` + `profile-assessment-editor.tsx`. **Non ancora né compilato né testato** (`npm ci` interrotto).

## Da fare (fase 2 → 3)

1. **Golden del resolver.** La suite si ferma su `test_a298_bw_progression.py::TestResolverStage::test_untested_profile_is_bit_for_bit_unchanged`. **Già verificato:** codice nuovo + catalogo vecchio = golden identico (exit 0), quindi la differenza viene solo dal dato di catalogo (cues + `hr_target` dentro l'output hashato), non da un cambio di selezione. Rigenera i golden toccati e committali con questa motivazione nel messaggio:
   - `python -m backend.tests.c272_golden_cases > /tmp/c272.json`, poi confronta con `backend/tests/fixtures/c272_resolver_golden.json`: devono cambiare solo le chiavi delle sessioni che contengono i 5 esercizi cardio (oggi 30 chiavi, 12 sessioni). Se cambia altro, **STOP**.
   - Stessa cosa per `a290_untested_golden.json` (`backend.tests.a290_untested_cases`) e `b364_untested_golden.json` (`backend.tests.b364_untested_cases`), se falliscono.
   - Poi la suite completa: `python -m pytest backend/tests -q`.
2. **Frontend:** `cd frontend && npm ci` (nel worktree, niente symlink), poi `npx tsc --noEmit`, `npm run lint`, `npx vitest run`. Attenzione:
   - `src/lib/types.ts` ora inizia con `import type { HrTarget } from "@/lib/hr-zones"`: verifica che non crei cicli (`hr-zones.ts` non importa da `types.ts`, quindi dovrebbe essere ok);
   - in `settings/page.tsx` l'import è finito sopra quello di React: riordinalo;
   - i test esistenti di `GuidedExerciseStep` non passano `hrMax` → il default `null` deve bastare.
3. **(Facoltativo, deciso con Daniele)** riga FC anche nella scheda esercizio `exercise-detail-sheet.tsx` (aperta da `exercise-card.tsx`): servirebbe `useUserState` lì dentro. Se lo fai, test.
4. **Immutabilità:** nessuna rigenerazione toccata, ma esegui comunque il test esistente sulle sessioni passate dopo la suite (regola di CLAUDE.md); il backfill di `week.py` salta done/skipped ed è coperto da `test_week_read_backfills_unplayed_custom_slot_only`.
5. **Docs nello stesso commit:** `docs/ROADMAP_CURRENT.md` (A316 ✅), `docs/user_guide_v1.md` (Settings → FC massima; il player mostra le fasce in bpm), `docs/vocabulary_v1.md` (`hr_target`, `hr_max_bpm`, `hr_max_source`), riga in `docs/ENGINE_ARCHITECTURE.md` se descrive i campi dell'istanza risolta.
6. Commit `A316: FC massima e fasce cardio in bpm` → `python scripts/sync_status.py` → push del **branch** → URL preview Vercel → **STOP: Daniele verifica la preview** (Settings: inserire 190/52; player: aprire la custom «Work — 4x4 norvegese (VO2max)» e vedere «Work 171-180 bpm · Recovery 124-142 bpm») → merge su main solo col suo OK.
7. Dopo il merge: impostare in prod `body.hr_max_bpm = 190`, `hr_rest_bpm = 52`, `hr_max_source = "measured"` per Daniele (da Settings o `PUT /api/state` con `body` **e** `assessment.body`). Poi pulizia del worktree.

## Dati di riferimento (Daniele)

- FCmax misurata ≥ 190 (Garmin, 07/08/2026); 4x4 del 16/10: picco 186 al 4° intervallo, ancora in salita → la vera è probabilmente 190-195. Da rivedere se un test o un 4x4 la superano.
- FC a riposo ~52.
- Con 190: Z2 114-133 · intervalli 171-180 · recupero 124-142.
- Tapis del 16/10: pendenza 6%, 10 km/h (già annotato nel completion log del giorno).
