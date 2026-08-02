# D269 — Audit di roadmap e documentazione

**Data:** 2026-08-02
**Tipo:** D (read-only sul codice; scrive solo documentazione)
**Branch:** `brief/D269-roadmap-docs-audit`
**Origine:** richiesta diretta di Daniele — «una bella pulizia e verifica approfondita della roadmap, e un'analisi di pulizia documentale e allineamento».

---

## 1. Metodo

Nessun finding è stato accettato perché la roadmap lo dichiarava. Ogni voce aperta è stata verificata contro tre fonti: il **codice** (grep/lettura), la **storia git** (`git log --grep` sui brief citati come pendenti) e lo **stato reale** (`user_state.json`, `openapi.json` di produzione, `scripts/gtm_funnel.py`).

Il criterio: un item resta aperto solo se oggi qualcuno lo può ancora osservare.

## 2. Debito che non esisteva più

| Voce | Come stava in roadmap | Verifica |
|---|---|---|
| **B176** (D172, 21 finding) | Open, effort L | **Implementato** in 4 commit `fix(B176)` che nominano i finding uno per uno. Il cappello della sezione dava anche B174/B175 come "pending": entrambi chiusi con commit `docs: mark B17x Done`. |
| D164 Frontend — `PHASE_LABELS` in 4 file | P2 aperto | 1 solo file (`lib/phase-labels.ts`), con test di regressione. |
| D164 Catalog — `age_under_16`, video placeholder | P2 aperto | 0 occorrenze di entrambi. Chiuso da B165e. |
| D164 Docs — intent 13+3, `closed_loop` path, `grip_transition` | P2 aperto | Tutti corretti in CLAUDE.md / vocabulary. |
| D211 **F6** — `phases[].weeks` è `null` | P3 aperto | Il campo **non esiste più**: le fasi hanno `duration_weeks` + `start_week`. |
| D211 **F7** — `goal.deadline` vuoto | P3 aperto | Popolato (`2026-09-01`). Il sintomo era di uno snapshot di aprile. |
| D211 **F5** — consumatori di `goal.primary_weakness` | P3 aperto | Nessun consumatore backend: si legge `assessment.self_eval.*`, che è la sede giusta. |
| D211 **F8** — `last_test_date` anomala | P3 cosmetico | Non riproducibile sullo stato attuale. |
| **D236** (Group 1-6) | Sezione con tabella | La tabella era **vuota**: solo l'header, da mesi. |
| **R160** — audio util duplicati | Backlog | `lib/beep.ts` è il modulo condiviso e **tutti e sei** i consumatori lo importano. |
| **B40** — branch develop/main | P3 UI polish | Superato da B196: policy branch + preview Vercel, applicata da un pre-commit hook. |

## 3. Due audit citati per anni che non esistono nel repo

- **D163** (67 finding frontend) — la roadmap puntava a `_archive/docs/frontend_audit_D163.md`. Il file non c'è: A198 lo ha cancellato *dicendo* di archiviarlo. Recuperabile solo da git (`git show be7ec67`).
- **D172** (25 finding) — nessun report, da nessuna parte, nemmeno in `_archive`. La roadmap stessa ammetteva che «il file `D172_findings_tracker.md` era pianificato ma mai creato». I due finding residui (D172-16, D172-21) sono quindi **non azionabili per ID**: nessuno può più leggere cosa fossero.

Lezione: un finding tracciato per ID senza il documento che lo definisce ha una vita utile che finisce quando finisce la memoria di chi l'ha scritto.

## 4. Finding nuovi

### 4.1 — `WELCOME-RECOVER-DEAD-END` 🔴 P2 (bug utente)

La landing pubblica offre *«Lost access? Recover with a code»* → `/onboarding/recover` → **stub di 12 righe** che fa `router.replace("/sign-in")`. Chi ha un codice `CLIMB-XXXX` non ha nessun posto dove usarlo.

Tre superfici descrivevano una feature con un solo pezzo funzionante:

| Superficie | Cosa dice | Realtà |
|---|---|---|
| `welcome-content.tsx:96` | «Recover with a code» | porta al login |
| `user_guide_v1.md` §18 | «Find it in Settings… tap Recover existing account → enter your code» | **zero** occorrenze di "recovery" nella UI di Settings |
| `api.ts:718` | «Recovery code functions removed — Clerk handles account recovery» | ✅ questa è vera |
| `user.py:122/154` | `POST /api/user/recovery-code`, `/api/user/recover` | **ancora vivi** |

Sanato qui il pezzo documentale (guida riscritta sulla verità: si rientra con l'email). Il codice resta da decidere: ricablare la pagina sugli endpoint esistenti, oppure togliere bottone + endpoint. Da chiudere **prima** del post r/climbharder — è l'unica CTA rotta su una pagina d'ingresso.

### 4.2 — Session Builder assente dalla guida utente ✅ chiuso qui

4 pagine e 7 endpoint `/api/custom-session/*`, e nella guida compariva solo di sfuggita nell'elenco dei tip «Did you know?». Aggiunta una sezione in §11. *(Il body-part picker invece era già documentato, sotto il nome «Body Part Training».)*

### 4.3 — Conteggio pagine sbagliato in CLAUDE.md ✅ chiuso qui

Il totale (47) era giusto, la scomposizione no: sommava 36 e **ometteva** session-builder (4 pagine), body-part-picker, `/demo`, `/offline` e le due pagine `/dev`. Diceva anche «16-step wizard» dove il wizard vero è di **12 step** (`ONBOARDING_STEPS`), con `welcome`/`install`/`start-week`/`recover` fuori dalla sequenza.

## 5. Stato GTM riscritto sui numeri

`scripts/gtm_funnel.py` al 2026-08-02: 14 registrati, 10 trial **tutti in scadenza il 5 agosto** (4 engaged fermi al 21-22 luglio, 6 mai loggati), 4 fermi al checkout, **0 paganti**, 3 cancellazioni storiche.

La sezione conteneva ancora il log operativo del 21-23 luglio con checkbox scaduti («domani 22/07: modmail r/climbharder»), una timeline «week 0-6» di aprile e una metrica di successo datata «fine aprile 2026». Riscritta: la coorte del re-lancio è persa, il canale è il problema, e **GTM-05 (post r/climbharder) è il prossimo passo attivo** — mai pubblicato pur essendo in bozza dal 22 luglio, e oggi con due condizioni tecniche in più rispetto ad aprile (`/assessment` pubblico via A262/A263, carry-over sistemato da B319).

## 6. Cosa è stato spostato, non cancellato

- `ROADMAP_v2.md` §D269 — testo integrale delle sezioni Audit Remediation, del log GTM e della Priority 2 (auth/pagamenti, ✅ da mesi).
- `_archive/docs/audit/` — 11 report chiusi e non più referenziati: A214/A215/A216 phase0, D-MEM-002, B183, B-SYNC-FIX, D176, D233, D234, D235, D237.
- Restano in `docs/audit/`: i report ancora citati da item aperti (D164/, D170, D-TESTUSER-VERIFY, D236/) e quelli recenti.

## 7. Rimane aperto (decisione di Daniele)

1. **`WELCOME-RECOVER-DEAD-END`** — ricablare o ritirare. Blocca GTM-05.
2. **Dimensione della roadmap** — 1069 → 957 righe, ma il target di `repo_hygiene.py` è ≤350 e non è raggiungibile potando: le ~450 righe restanti sono backlog esplorativo legittimo (Backlog/exploration 118, Future ×3, v2+ Deferred, v3). Proposta: separare `docs/ROADMAP_BACKLOG.md` per ciò che non è schedulato, lasciando in `ROADMAP_CURRENT.md` solo Open + priorità attive — oppure alzare il target dello script, che oggi produce un warning permanente che nessuno può risolvere.
3. **D172-16 / D172-21** — riaprire un audit mirato o dichiararli chiusi: per ID non sono recuperabili.
