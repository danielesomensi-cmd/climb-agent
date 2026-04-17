# D-ANALYTICS-DROPOFF — Funnel drop-off diagnosis

**Data run:** 2026-04-17
**Tipo:** D (audit read-only, zero scritture)
**Script:** `scripts/diagnose_dropoff.py`
**Comando:** `source .venv/bin/activate && python scripts/diagnose_dropoff.py`

---

## Schema autodiscovery

```
users  (rows=9)
  - clerk_id
  - created_at
  - state
  - updated_at
  - user_id

session_logs  (rows=0)          ← EMPTY in prod — vedi nota sotto
  (empty — column list unknown)

subscriptions  (rows=1)
  - cancel_at_period_end
  - created_at
  - current_period_end
  - current_period_start
  - id
  - status
  - stripe_customer_id
  - stripe_subscription_id
  - trial_end
  - trial_start
  - updated_at
  - user_id
```

### Finding collaterale critico

`public.session_logs` contiene **0 righe in produzione**. Le sessioni completate non passano per questa tabella — risiedono dentro `users.state.session_completion_log` (JSONB array per utente). Lo script conta da lì (source of truth), e mantiene in parallelo una colonna shadow `Sessions (logs)` per evidenziare la divergenza.

Implicazioni:
- Ogni query analytics su `session_logs` (es. tentativi via SQL editor) restituisce risultati falsi.
- Se c'è stata un'intenzione di popolare `session_logs` come log event-sourced, non è live.

## Validation gate

Atteso: Daniele ≈ 30 sessioni, Christie ≈ 9.

```
✓ Daniele: n_sessions=31 (expected 30, Δ=1)
✓ Christie: n_sessions=9 (expected 9, Δ=0)
```

JOIN key (`users.user_id` ↔ sorgente `state.session_completion_log[].status=='done'`) validata: entrambi dentro ±3.

## Detail table (8 utenti, escluso founder)

Sort: stage ASC (peggiore in alto), poi days_since_signup DESC.

| Email | Name | Stage | Sessions (state) | Sessions (logs) | Last Session | Sub Status | Days Since Signup |
|-------|------|-------|------------------|-----------------|--------------|------------|-------------------|
| romitodavid@gmail.com | David R | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 24 |
| pewen.outdoors@gmail.com | Agustin Toro | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 16 |
| cesar.e.meric@gmail.com | — | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 16 |
| paul.cample@gmail.com | Paolo Campli | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 16 |
| tabithamann90@gmail.com | Tabitha Mann | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 16 |
| arthur.pepin11@gmail.com | — | 4_HAS_WEEK_PLANS | 0 | 0 | — | — | 8 |
| daniele.somensi@ferrero.com | — | 5_HAS_SUB | 0 | 0 | — | trialing | 27 |
| ckb.palmer@gmail.com | Palmer Christie | 6_ACTIVE | 9 | 0 | 2026-03-30 | — | 32 |

## Stage distribution (escluso founder)

```
1_SIGNUP_ONLY        0 users
2_HAS_ASSESSMENT     0 users
3_HAS_MACROCYCLE     0 users
4_HAS_WEEK_PLANS     6 users
5_HAS_SUB            1 users
6_ACTIVE             1 users
------------------
TOTAL                8 users
```

## Diagnostic interpretation

```
Pre-plan drop-off (stages 1-2):       0 users (0%)
Post-plan no-session (stages 3-4):    6 users (75%)
Has subscription, never logged (5):   1 users (12%)
Active (stage 6):                     1 users (12%)
```

**Modo di drop-off dominante: post-plan confusion.**

6 utenti su 8 (75%) hanno completato l'intero onboarding — profilo, assessment, goal, macrociclo, e settimana pianificata — ma non hanno mai aperto una singola sessione. Nessuno si è bloccato prima della generazione del piano: il problema non è nel wizard, è nel momento **subito dopo**. L'utente finisce l'onboarding, vede il piano, e non clicca sul primo allenamento.

Ipotesi compatibili con questi dati (non verificabili senza telemetria frontend, che oggi non abbiamo — `event_logs` è ugualmente vuota):
- Il "what's next" dopo onboarding è ambiguo (nessun CTA forte verso Today/Session).
- Il primo allenamento proposto appare troppo pesante o intimidatorio.
- Frustrazione da paywall anticipato (ma qui 5/6 utenti stage-4 non hanno nemmeno una sub → esclude il paywall-first come unica causa).

Altri rilevanti:
- 1 utente (`daniele.somensi@ferrero.com`) è a stage 5 (trialing, ancora nessuna sessione loggata) — verosimilmente account test dello stesso founder con email di lavoro, non un segnale di mercato.
- 1 utente effettivamente attivo: Christie (9 sessioni, ultima 2026-03-30, 32 giorni di permanenza).

**Importante:** questo è soltanto diagnosi. La soluzione va decisa separatamente in un A-brief dopo revisione (guided first session vs CTA "Start first workout" vs telemetria di funnel per confermare l'ipotesi, ecc.).

## Note operative

- Script read-only, idempotente, rieseguibile come diagnostic trend-tracker.
- Prereq: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` in `.env` (già presenti). `CLERK_SECRET_KEY` opzionale (arricchisce nome/email; senza, lo script continua con solo user_id/clerk_id).
- Nessuna libreria aggiunta a `requirements.txt`: `supabase-py`, `requests`, `python-dotenv` già presenti via dipendenze esistenti.
