# D241 — Audit latenza startup / azioni (read-only)

**Tipo:** D (audit, read-only) · **Rischio:** nessuno (nessuna modifica al codice) · **Data:** 2026-06-04 · **Utente di test:** Daniele (`7ea9f0ee-…771e`)

## TL;DR

Il lag di 2-3s **non è cold start**. Railway non dorme (health warm 0.6s ≈ cold 0.85s). La causa radice è una sola: **`user_state` è cresciuto a ~2.0 MB** e **ogni** endpoint che chiama `load_state()` paga ~1.7s fissi per scaricare + deserializzare quel JSONB da Supabase. Prova schiacciante: `/api/state/status` restituisce **29 byte** ma ha TTFB **2.29s** — niente payload, niente resolve, solo il fetch dello stato gonfio.

L'86% dei 2 MB sono `week_plans` (19 settimane di piani risolti accumulati), più un duplicato `current_week_plan` (233 KB).

---

## 1. Cold vs warm (numeri misurati)

| Endpoint | Cold (1ª chiamata) | Warm | TTFB warm | Payload | Note |
|---|---|---|---|---|---|
| `/health` | 0.85s | 0.61s | 0.61s | ~90 B | nessun accesso DB |
| `/api/state` | 5.11s | 3.5–4.1s | **2.76s** | **1.89 MB** | `load_state` + transfer 1.9 MB |
| `/api/week/1` | 3.75s | 3.3s | 2.39s | 206 KB | `load_state` + resolve |
| `/api/week/2` | — | 3.36s | 2.81s | 149 KB | idem |
| `/api/state/status` | — | 2.29s | **2.29s** | **29 B** | 🔑 solo `load_state`, zero payload |

**Lettura chiave:**
- warm ≈ cold → **il cold start NON è il problema dominante** (penalità cold ~250 ms al massimo).
- `/health` (0.6s, no DB) vs `/api/state/status` (2.29s, 29 B di risposta) → il **~1.7s di differenza è il costo di `load_state()`** che fetcha/deserializza ~2 MB di JSONB. Questo costo è pagato da **ogni** azione dell'utente (mark done/skip, apertura pagina, replan…), ed è esattamente il lag "su prime azioni" che Daniele percepisce.

---

## 2. Composizione di `user_state` (2.0 MB)

```
TOTALE                 2,015,871 B (1969 KB)
  week_plans           1,734,640 B   86.0%   (19 settimane)
  current_week_plan      233,631 B   11.6%   ← DUPLICATO di week_plans["2026-06-01"] (byte-identico)
  session_completion_log  10,807 B    0.5%
  free_sessions            8,537 B    0.4%
  …resto < 0.3% ciascuno
```

Dettaglio `week_plans`: 19 settimane, le più pesanti 150–233 KB ciascuna (sessioni completamente risolte: warmup/cooldown/prescrizioni/blocchi). Solo la settimana corrente (`2026-06-01`) e la prossima servono nell'hot path; le 17 settimane passate sono storia immutabile che **non serve trasferire né rideserializzare ad ogni richiesta**.

---

## 3. Cause classificate (impatto decrescente)

### Causa #1 — `user_state` gonfio (~2 MB), 86% week_plans · **ROOT CAUSE**
**Evidenza:** `/api/state/status` 29 B → 2.29s TTFB; composizione stato sopra; `read_state()` (`backend/engine/storage_supabase.py:79`) fa un singolo SELECT che però ritorna l'intero JSONB. **Ogni** endpoint via `load_state()` paga ~1.7s.
**Impatto:** colpisce TUTTE le azioni (apertura app + ogni mark/replan/navigazione). È la fonte reale del lag percepito.

**Fix consigliati (dal più sicuro al più strutturale):**
- **(a) Rimuovere il duplicato `current_week_plan`** dallo stato (è byte-identico a `week_plans["<settimana corrente>"]`). −11.6% gratis se i consumer leggono già da `week_plans`. **Effort XS · rischio basso · backend-only** — *ma verificare prima ogni lettore di `current_week_plan` (è zona `week.py`/resolve, quindi richiede fase di analisi + STOP).*
- **(b) Archiviare le week_plans passate** in una colonna/tabella Supabase separata, caricata lazy solo quando si apre `/api/week/{passata}`. `load_state()` dell'hot path scende a ~corrente+prossima (~250 KB invece di 2 MB). Preserva l'immutabilità (i dati non vengono toccati, solo rilocati). **Effort M · rischio medio · backend** — tocca schema `user_state` + `load_state`/`save_state` → **fase di analisi + STOP obbligatori** (CLAUDE.md: schema changes, immutabilità sessioni passate).
- **(c) Non persistere il dettaglio risolto completo nelle settimane passate** (tenere solo esito: `exercise_id`, loads, feedback, status — ciò che serve all'immutabilità — e ri-risolvere il dettaglio on-demand alla visualizzazione). Più invasivo, riduce di più. **Effort M-L · rischio medio-alto** (resolve_session + immutabilità) → STOP obbligatorio.

### Causa #2 — Nessuna compressione gzip sulle risposte
**Evidenza:** header risposta senza `content-encoding`; `curl --compressed` scarica comunque 1,894,048 B pieni. Rapporto gzip misurato: **state 8.7×** (1849 KB → 212 KB), **week 7.3×** (206 KB → 27 KB).
**Impatto:** ~1s di transfer sul download di `/api/state` all'apertura (mobile/egress Railway). Non aiuta il TTFB di `load_state` (payload piccoli come status restano lenti per il fetch DB).
**Fix:** aggiungere `GZipMiddleware` (Starlette) in `backend/api/main.py`. **Effort XS · rischio nullo · backend-only (push diretto).**

### Causa #3 — Waterfall frontend: `/api/state` → `/api/week/0` in serie all'apertura
**Evidenza:** `today/page.tsx` — `useUserState()` e `useWeekPlan(0)` entrambi gated da `authReady`, ma la week è di fatto serializzata dopo lo state; inoltre retry 401 con +500 ms (`api.ts:48-53`). Con costo fisso ~2.3s per chiamata, due chiamate in serie = ~4–5s prima del primo render utile.
**Impatto:** raddoppia il costo fisso all'apertura.
**Fix:** lanciare `/api/state` e `/api/week/0` in **parallelo** se la week non dipende dal risultato dello state (auth è già su token Clerk, non sullo state). Inoltre spostare `useSubscription()` in React Query (oggi fetch indipendente che gate `canInteract`). **Effort S · rischio basso · FRONTEND → branch `brief/…` + preview Vercel obbligatori** (regola B196).

### Causa #4 — `/api/week/{n}` ri-risolve le sessioni + catalog non cachati (cold path)
**Evidenza:** `resolve_session.py:37-39` `load_json()` senza `@lru_cache`; `exercises.json` (~200 KB) ricaricato da disco 6+ volte per richiesta week (una per sessione), template 18–30 volte (`resolve_session.py:1353,1471`); `deepcopy(state)` per sessione in `week.py:82` (~50–100 ms su 2 MB). Quando la week è già in cache il path è veloce (~250 ms), ma le settimane fredde/forzate pagano tutto.
**Impatto:** secondario rispetto a #1 (il TTFB week è comunque dominato da `load_state`), ma ~0.5–1s sulle week non ancora risolte.
**Fix:** `@lru_cache`/cache a livello modulo su `load_json()` (come già fatto in `custom_session.py:28` e `body_part_picker.py:48`); evitare `deepcopy` integrale per-sessione. **Effort S · rischio basso · backend-only** — *ma `resolve_session.py` è modulo ad alto rischio → fase di analisi + STOP prima di implementare.*

### Causa #5 — `/api/state/status` deserializza l'intero stato per un solo flag
**Evidenza:** ritorna 29 B (`is_macrocycle_stale`) ma TTFB 2.29s perché chiama `load_state()`.
**Impatto:** ogni polling di dirty-state paga 2.3s.
**Fix:** materializzare `is_macrocycle_stale` come campo/colonna leggera interrogabile senza caricare tutto lo stato. **Effort S · rischio basso · backend** (tocca storage → analisi prima). Nota: diventa marginale una volta ridotta la dimensione dello stato (causa #1).

---

## 4. Quick win

**🏆 Quick win a impatto/sforzo migliore: abilitare `GZipMiddleware` (Causa #2).**
- Effort **XS** (poche righe in `main.py`), **rischio nullo**, **backend-only → push diretto a main**.
- Taglia il download di `/api/state` da 1.89 MB a ~212 KB (8.7×) → −~1s all'apertura, su tutti gli endpoint.

⚠️ **Onestà sull'impatto:** gzip risolve il *transfer*, **non** il costo fisso ~1.7s di `load_state` che è ciò che rende lente le *azioni* (payload piccoli). Per il lag su "prime azioni" l'unica leva reale è **ridurre la dimensione dello stato (Causa #1)**.

**Sequenza consigliata:**
1. **Oggi, zero rischio:** gzip (#2) → push diretto.
2. **Prossimo, alto valore, sicuro:** rimuovere il duplicato `current_week_plan` (#1a) — previa verifica consumer + STOP.
3. **Vero fix strutturale:** archiviazione lazy delle week_plans passate (#1b) — brief dedicato con fase di analisi + STOP (schema + immutabilità).
4. **Frontend:** parallelizzare state/week (#3) su branch + preview.
5. **Backend cache:** `@lru_cache` su `load_json` (#4) — con analisi su resolve_session.

---

## Vincoli rispettati
- Read-only: nessuna modifica al codice, solo questo report.
- Verifica utente: `user.name == "Daniele"` confermata sullo stato analizzato.
- Nessun modulo ad alto rischio modificato (solo letti dove rilevanti al waterfall).
