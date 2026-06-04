# D242 — Audit: lazy-archive past `week_plans` (read-only)

**Tipo:** D (audit, read-only) · **Rischio di questo brief:** nessuno · **Rischio della feature risultante:** ALTO (tocca persistenza `week.py`/`resolve_session`/`macrocycle_archive` + invariante immutabilità) · **Data:** 2026-06-04 · **Assorbe:** B256 (rimozione `current_week_plan`)

> ⚠️ Questo è un audit. **Nessun archiving implementato.** L'A-brief risultante è high-risk → protocollo STOP obbligatorio, sequenziale, niente parallelo.

---

## 1. Cifre stato verificate sul live (utente Daniele, `7ea9f0ee…`)

| Voce | Valore | % stato |
|---|---|---|
| **Totale `user_state`** | 2,015,871 B (1969 KB) | 100% |
| **`week_plans`** | 1,734,640 B | **86.0%** — 19 settimane |
| **`current_week_plan`** | 233,631 B | 11.6% — byte-identico a `week_plans["2026-06-01"]` ✓ |

D241 confermato. Distribuzione settimane: da 2,7 KB (non risolte) a 233 KB (risolte). Oggi = 2026-06-04; Monday corrente **N = 2026-06-01**; **N-1 = 2026-05-25**.

**Proiezione riduzione** (archiviare < N-1 *e* eliminare `current_week_plan`):

| | Bytes |
|---|---|
| Hot tenuto (N-1, N, N+1 = 3 settimane) | 371,385 B |
| **Archiviabile (16 settimane < N-1)** | **1,362,951 B (1331 KB)** |
| Dedup `current_week_plan` | 233,631 B |
| **Hot state finale** | **419,289 B (409 KB)** → **−79%** |

Questo taglia il costo fisso `load_state()` (~1.7s di fetch+deserialize Supabase di 2MB) che D241 ha identificato come la radice del lag sulle azioni. L'archivio cresce in **cold store** (non caricato per-request) → non impatta la latenza.

---

## 2. Access map `week_plans` / `_prev_week_plan`

R = read, W = write. "Whole-dict" = riscrive/filtra l'intero dict (path pericolosi).

| File:Line | Funzione | R/W | Settimane | Lookback >1? | Note |
|---|---|---|---|---|---|
| deps.py:65-68 | `invalidate_week_cache` | W | **WHOLE-DICT** | no | tiene `k < today`; stasha old `current_week_plan`→`_prev_week_plan`. Chiamata da `/macrocycle/generate` |
| deps.py:79-82 | `invalidate_future_week_cache` | W | **WHOLE-DICT** | no | tiene `k <= current_monday`; nessun caller prod (solo test) |
| macrocycle.py:119-130 | `_clear_week_cache_for_new_cycle` | W | **WHOLE-DICT** | no | tiene `k < new_start_date`. Chiamata da `/macrocycle/start-new-cycle` |
| weekly_override.py:86-88 | `put_weekly_override` | W | single (pop) | no | rimuove 1 settimana per forzare regen; sicuro |
| week.py:276,286 | `get_week` | R | single (key) | no | cache-hit non-force |
| week.py:381 | `get_week` | R | **N-1** | no (esatto 1) | `week_plans.get(prev_start)` per spacing cross-week (B161) |
| week.py:437-440 | `get_week` | W | single (+legacy) | no | scrive plan generato + mirror `current_week_plan` |
| week.py:425,428,433 | `get_week` (merge) | R/W | `_prev_week_plan` | no | merge B114 dopo regen macrociclo, poi `pop` |
| feedback.py:92,106 | `post_feedback` | R/W | current (legacy) | no | mark_done inline primario |
| feedback.py:111,119,133 | `post_feedback` | R/W | single/target_monday | no | sync `week_plans[start]` + fallback B216 |
| feedback.py:236,244,278,280,326 | `post_feedback` | R/W | current | no | sync actual_exercises / duration / adaptive replan |
| replanner.py:86-99 | `persist_week_plan` | W | single (+legacy) | no | scrive plan modificato |
| body_part_picker.py:161,186 | `start` | R/W | current | no | inserisce sessione body-part |
| report_engine.py:133-148 | `_find_week_plan` | R | **qualsiasi** | **SÌ (illimitato)** | report navigabile a qualunque settimana passata |
| **resolve_session.py:735-750** | `load_recent_exercise_ids` | R | **3 più recenti** | **SÌ (3)** | recency/dedup esercizi; `sorted(reverse)[:3]` |
| **macrocycle_archive.py:48-61** | `_planned_session_count` | R | **intero ciclo** | **SÌ (tutto)** | conteggio planned all'archiviazione del macrociclo |

### Path "whole-dict" (i pericolosi)
`invalidate_week_cache`, `invalidate_future_week_cache`, `_clear_week_cache_for_new_cycle`. Tutti **già preservano il passato** filtrando per data — ma rimpiazzano `state["week_plans"]` con un nuovo dict. Un archivio separato deve essere coordinato qui: questi non devono cancellare l'archivio né perdere settimane non ancora archiviate.

### Consumer che leggono 2+ settimane indietro (rompono il confine N-1)
1. **`load_recent_exercise_ids` (resolve_session)** — `RECENCY_LOOKBACK_WEEKS=3`. Prende i 3 **key più recenti presenti** in `week_plans` (non N-2 assoluto), solo sessioni `status=="done"`, raccoglie `exercise_id`. *Degrada* (meno varietà), non crasha, se ne trova meno. **Tocca la determinismo dell'engine** → va preservato esattamente.
2. **`_planned_session_count` (macrocycle_archive)** — itera l'intero `week_plans` per il conteggio planned del ciclo, all'avvio di un nuovo ciclo. Gira **prima** del clear (macrocycle.py:199 < 268). Se le settimane passate sono già in cold store, sottoconta.

---

## 3. Consumer di dati storici (cosa si rompe se il passato sparisce dall'hot state)

**DEVONO migrare a leggere dall'archivio:**
- **`GET /api/week/{n}` (week.py)** — il frontend `/week` permette di navigare a **qualsiasi** settimana del macrociclo (prev/next, week picker). Una settimana passata archiviata → cache-miss → **rigenerazione** (vedi §4). Crux assoluto.
- **`GET /api/reports/weekly?week_start=` (report_engine `_find_week_plan`)** — il frontend `/reports/weekly` naviga a qualsiasi settimana. Adherence/load/difficulty/progression di settimane passate.
- **`load_recent_exercise_ids` (resolve_session)** — recency dedup (determinismo).
- **`_planned_session_count` (macrocycle_archive)** — stats di completamento del ciclo.

**NON impattati (log separati da `week_plans`):**
- `session_completion_log` — append-only, **non troncato** (storia completa di done/skipped). È la fonte durevole dell'adherence.
- `feedback_log` — **troncato a 7** (adaptive_replan.py:88) → ⚠️ il dettaglio feedback storico (`feedback_summary`, `exercise_feedback`) vive **solo dentro `week_plans[past]`**. Archiviare il passato sposta l'unica copia → i report passati DEVONO leggere l'archivio.
- `free_sessions`, `outdoor_log` — strutture indipendenti.
- `macrocycle_history` — riepilogo compatto (~4KB) già separato, resta hot.

---

## 4. Il crux dell'invariante: rigenerazione di settimane passate

**Oggi le settimane passate sono sempre in `week_plans` → la cache fa sempre hit → nessuna rigenerazione.** È un invariante *incidentale*, non difeso da un guard.

In `week.py:220-441` non esiste alcun guard "non rigenerare settimane passate". `is_current_week` (riga 273) protegge solo la corrente. Per una settimana passata:
- cache-miss (riga 287) → `week_plan=None`
- riga 311 → riga 320: `today_str = None` (perché non è current) → il planner **non salta i giorni passati** (commento B95)
- riga 383: `generate_phase_week()` → **rigenera tutti i 7 giorni da zero**
- `regenerate_preserving_completed` (416) richiede `old_plan` = `week_plans.get(key)` = **None se archiviata** → non scatta
- `merge_prev_week_sessions` (428) gira solo `if is_current_week` → non scatta

→ **Archiviare una settimana passata + l'utente ci naviga = settimana passata rigenerata, sessioni completate/feedback/load PERSI.** Viola direttamente il principio non negoziabile.

**Condizione di sicurezza (necessaria nell'A-brief):** l'archivio deve essere caricato nel **ramo di lettura cache** (week.py:283-296) *prima* del ramo di rigenerazione, e una settimana passata risolta dall'archivio non deve MAI raggiungere `generate_phase_week()`. Equivalente: aggiungere un guard esplicito "se la settimana è < N e proviene dall'archivio, servila read-only; mai rigenerare".

---

## 5. Opzioni di design

### Opzione A — Colonna/tabella JSONB separata `archived_week_plans` (cold store) — **CONSIGLIATA**
Le settimane < confine-hot vivono in una struttura separata (colonna JSONB `archived_week_plans` sulla riga utente, o tabella `week_archive(user_id, week_start, plan)`), **non caricata da `load_state()`**. Caricata on-demand solo da: `GET /api/week/{past}`, report, recency lookback, archive del ciclo.
- **Pro:** dati integri al 100% (nessuna perdita di dettaglio); hot state ~409 KB; immutabilità banale (cold store è write-once, mai rigenerato). Allineato a Supabase JSONB già in uso.
- **Contro:** richiede un layer di accesso archivio (`read_archived_week`, `archive_week`) e il wiring dei 4 consumer. Una query extra Supabase quando si apre una settimana passata (accettabile: evento raro).

### Opzione B — Trim + summary (tieni N settimane hot, riepilogo compatto per le più vecchie)
Le settimane vecchie collassano in un sommario (adherence %, load totale, grado) e si **scarta il dettaglio risolto** (warmup/cooldown/exercise_instances/feedback per-esercizio).
- **Pro:** nessun secondo store; hot state piccolo.
- **Contro:** **perdita irreversibile di dati** — i report storici dettagliati e `load_recent_exercise_ids` non funzionano più; il dettaglio sessione passata non è più visualizzabile. Confligge con lo spirito dell'immutabilità (i dati completati non vanno persi). **Sconsigliata.**

### Opzione C — Solo-risposta (escludi `week_plans` passate dal payload `/api/state`)
Non risolve nulla: i dati restano nel JSONB, `load_state()` paga comunque il fetch/deserialize. Post-gzip il transfer è già piccolo. **Non risolve la radice.** Scartata.

### Confine hot canonico assodato
L'ipotesi del brief "N e N-1, archivia N-2+" è **quasi corretta ma va estesa**: `load_recent_exercise_ids` vuole fino a 3 settimane di sessioni *done*. Due strade nell'A-brief:
- **C1 (consigliata):** confine hot = **{N-1, N, future}**, e `load_recent_exercise_ids` carica la finestra di recency dall'archivio (richiamo esplicito), preservando il comportamento a 3 settimane. Hot minimo, determinismo intatto.
- **C2:** confine hot = **{N-2, N-1, N, future}** (4 settimane), nessun cambio a resolve_session. Più semplice ma hot leggermente più grande (~+150KB) e il confine "scivola" comunque (le settimane diventano N-3 col tempo → vanno archiviate → si ricade in C1). 

Raccomando **A + C1**.

---

## 6. Prova dell'invariante (per A + C1)

Sia *archive* lo store cold write-once; *hot* = `week_plans` con sole {N-1, N, future}.

1. **Nessun path di archiviazione/caricamento può rigenerare una sessione archiviata.**
   - L'archiviazione è un `move` puro (copia il dict immutato in *archive*, rimuove la key da *hot*). Nessuna chiamata a planner/resolver.
   - La lettura archivio (`read_archived_week`) restituisce il dict così com'è. Con il guard §4, `get_week` per una settimana passata serve l'archivio e **bypassa** `generate_phase_week`. ∎
2. **Ogni path replanner/device-switch/equipment è read-only verso le settimane archiviate.**
   - replanner/feedback/body_part_picker/weekly_override scrivono solo su `week_plans[current/target]` (target = N o N-1, sempre hot — vedi access map: nessuno scrive su key < N-1).
   - device-switch/equipment-change agiscono via `_auto_resolve`/`_cache_completed_resolved` che girano sulla settimana richiesta; con il guard, una settimana archiviata non viene ri-risolta (è già `resolved` e immutabile). `_cache_completed_resolved` (week.py:115, commento riga 46) già protegge le sessioni passate dal re-resolve su device-switch.
   - I 3 path whole-dict filtrano per data e **non toccano** l'archivio separato → non possono resuscitare+mutare settimane archiviate. ∎
3. **Ogni consumer storico è identificato e migrato** (§3): `get_week`, `report_engine._find_week_plan`, `load_recent_exercise_ids`, `macrocycle_archive._planned_session_count`. Se uno non viene migrato → mostra vuoto/sottoconta (fail silenzioso) → è nella checklist §7.
4. **Crescita:** *archive* cresce ~150–230 KB per settimana risolta (~260 KB/mese per Daniele, heavy user; il dato memo "260KB/anno" è sottostimato). Vive in cold store → **non impatta la latenza per-request**. Pulizia: nessuna necessaria (è storia); opzionale prune di macrocicli chiusi oltre N mesi, ma fuori scope iniziale. ∎

---

## 7. Migration risk list + outline implementazione (STOP-gated, NON implementato)

**Rischi:**
- R1 (critico) — regen settimana passata se il guard §4 manca o l'archive-read è a valle del ramo regen. *Mitigazione:* test che naviga a una settimana archiviata e asserisce identità byte-per-byte + assenza di chiamata a `generate_phase_week` (mock/spy).
- R2 — `macrocycle_archive._planned_session_count` sottoconta se gira dopo che il passato è archiviato. *Mitigazione:* farlo leggere hot+archive, o calcolarlo all'archiviazione della settimana.
- R3 — `load_recent_exercise_ids` cambia output deterministico (varietà esercizi) se non carica la recency dall'archivio. *Mitigazione:* test di determinismo prima/dopo su stato reale.
- R4 — i 3 path whole-dict che rimpiazzano `week_plans` potrebbero orfanare o duplicare l'archivio durante regen/new-cycle. *Mitigazione:* rivedere ognuno; l'archiviazione deve essere idempotente.
- R5 — migrazione degli stati esistenti: 16 settimane già nel JSONB hot vanno spostate nell'archivio al primo load. *Mitigazione:* migrazione one-shot in `load_state` (come m001), con `assert name=='daniele'` se eseguita come script su dati reali; idempotente; **mai** rigenerare durante la migrazione (move puro).
- R6 — `current_week_plan` (B256): rimuoverlo qui. I 10 reader vanno reindirizzati a `week_plans[this_monday()]` via helper unico; lo stash `_prev_week_plan` va alimentato da `week_plans[N]`. È parte dell'A-brief, dopo che l'hot è ridotto.

**Outline (sequenziale, ogni passo dietro STOP):**
1. Layer archivio: `archive_week(state, key)`, `read_archived_week(uid, key)`, store (colonna JSONB `archived_week_plans` o tabella). Test isolati.
2. Guard §4 in `get_week`: ramo di lettura → hot → archive → solo se entrambi vuoti e settimana ≥ N, rigenera. Test anti-regen.
3. Migrare i 4 consumer storici (week, report_engine, resolve_session recency, macrocycle_archive).
4. Trigger di archiviazione: al rollover/`get_week`, spostare le settimane < N-1 da hot ad archive (idempotente). Coordinare con i 3 path whole-dict.
5. Migrazione one-shot stati esistenti + rimozione `current_week_plan` (B256, helper unico).
6. Suite completa + test invariante dedicati (anti-regen, determinismo recency, conteggio archive, immutabilità su device-switch verso settimana archiviata).

---

## 8. Stima effort A-brief

**M–L** (≈ 1.5–2.5 giornate). Tocca moduli high-risk (`week.py` persistenza, `resolve_session`, `macrocycle_archive`, schema `user_state`, storage Supabase) → richiede analisi + STOP per ogni step, branch + preview (il frontend `/week` e `/reports/weekly` vanno verificati su settimane passate), e una batteria di test sull'invariante. Non frazionabile in un singolo B. Payoff: hot state **−79%** (2.0MB → ~409KB), che attacca direttamente il lag sulle azioni (causa radice D241).

---

## Vincoli rispettati
- 100% read-only; unico output questo report.
- Verifica utente: `user.name.strip() == "Daniele"` confermata sullo stato live.
- Nessun archiving implementato. L'A-brief erediterà il protocollo high-risk (STOP, sequenziale).
