# D176 — React Query Invalidation Map

**Data:** 2026-04-07 | **Tipo:** D (read-only audit) | **Stato:** ✅ Done  
**Dipende da:** D175 (performance audit)  
**Usato da:** A187 (React Query implementation)

---

## 1. GET Endpoints — Cache Keys

| Cache Key | Endpoint | Usato da | Descrizione payload | Stale tolerance |
|-----------|----------|----------|---------------------|-----------------|
| `['state']` | `GET /api/state` | today, week, plan, settings, guided, start-week | Full user state (profile, equipment, macrocycle, assessment, availability, spots) | **0** — invalida subito dopo ogni mutazione |
| `['state', 'status']` | `GET /api/state/status` | plan | `{is_macrocycle_stale: boolean}` | **0** — stesso dato di state |
| `['week', n]` | `GET /api/week/{n}` | today (n=0), week (n=0..±N), plan (n=0) | Week plan completo: slots, sessions, test badges, load scores | **0** — invalida subito dopo replanner/feedback |
| `['outdoor', 'spots']` | `GET /api/outdoor/spots` | settings, today, week, outdoor, quick-add | Lista crag spots utente | **low** — cambia solo su add/delete spot |
| `['outdoor', 'sessions']` | `GET /api/outdoor/sessions` | today, week, outdoor | Tutte le sessioni outdoor (opzionalmente da data) | **low** — cambia su POST/PUT/DELETE outdoor log |
| `['outdoor', 'log', date]` | `GET /api/outdoor/log/{date}` | today, outdoor | Sessione outdoor per data specifica | **low** — cambia su write per quella data |
| `['outdoor', 'stats']` | `GET /api/outdoor/stats` | outdoor | Stats aggregate (totali, inviati, grade histogram) | **low** — cambia su qualsiasi write outdoor |
| `['free-session', 'surfaces']` | `GET /api/free-session/surfaces` | free-session | Superfici disponibili + lista palestre utente | **high** — cambia solo su add/remove gyms |
| `['free-session', 'presets', surfaceId]` | `GET /api/free-session/presets?surface={id}` | free-session | Preset per superficie (grade target, tip, fase) | **high** — quasi statico |
| `['free-session', 'history', date]` | `GET /api/free-session/history?date={date}` | today, week | Free sessions in una data | **low** — cambia su finish/delete free session |
| `['reports', 'weekly']` | `GET /api/reports/weekly` | reports/weekly | Report settimanale: adherence, load, distribuzione | **low** — cambia su qualsiasi evento settimana |
| `['quotes', 'daily', context]` | `GET /api/quotes/daily?context={ctx}` | today | Quote giornaliera per contesto | **high** — statica per fase, cache 24h |
| `['catalog', 'sessions']` | `GET /api/catalog/sessions` | quick-add-dialog | Tutti i template sessione | **high** — immutabile a runtime |
| `['catalog', 'exercises']` | `GET /api/catalog/exercises` | session/[id] | Tutti gli esercizi del catalogo | **high** — immutabile a runtime |
| `['replanner', 'suggest', date, location]` | `GET /api/replanner/suggest-sessions` | quick-add-dialog | Sessioni suggerite per data + location | **low** — cambia dopo mutazioni week plan |
| `['onboarding', 'defaults']` | `GET /api/onboarding/defaults` | onboarding/locations | Opzioni default equipment/locations | **high** — statico |
| `['subscription', 'status']` | `GET /api/subscription/status` | use-subscription hook | `{status, is_active, trial_days_remaining, can_interact}` | **high** — poll ogni 5min, non invalida su mutazioni |
| `['weekly-override', weekStart]` | `GET /api/weekly-override/{weekStart}` | (non ancora usato in UI) | Override disponibilità per settimana | **low** — cambia su PUT/DELETE override |

---

## 2. Mutations — Catalogo completo

### Replanner e Week Plan

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/replanner/events` | POST | today/page.tsx, week/page.tsx | Mark done, mark skipped, move session, change gym, remove session, complete other activity, undo events | `week_plans[current_week]` — stato sessioni |
| `POST /api/replanner/override` | POST | today/page.tsx, week/page.tsx | Dialog "Replan" — cambia location/intent per uno slot | `week_plans[current_week]` — sostituisce sessione |
| `POST /api/replanner/quick-add` | POST | quick-add-dialog.tsx | Dialog "Aggiungi sessione" — sceglie sessione + slot | `week_plans[current_week]` — aggiunge slot |
| ~~`POST /api/outdoor/convert-slot`~~ | POST | today/page.tsx, week/page.tsx | "Converte" slot indoor in outdoor | **Nessuna mutazione**: ritorna solo `{date, new_location, suggestions}`. È una query mascherata da POST. La vera mutation arriva quando l'utente sceglie una suggestion → `quick-add` o `override`. **Verificato in A187 Phase 0** |
| `POST /api/session/add-exercise` | POST | session/[id] page | Aggiunge esercizio a sessione esistente | `week_plans[current_week]` — esercizi slot |
| `POST /api/session/remove-exercise` | POST | session/[id] page | Rimuove esercizio da sessione | `week_plans[current_week]` — esercizi slot |
| `POST /api/session/resolve` | POST | session/[id] page | Apertura/refresh sessione guidata | Risolve template → esercizi concreti (no state change) |

### Feedback

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/feedback` | POST | today/page.tsx, week/page.tsx, guided/page.tsx | Invia feedback RPE/carico/grade o misurazioni test | `user_state.feedback`, `user_state.progression`, carico next session — cascata su week_plan |

### State / Settings

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `PUT /api/state` | PUT | settings/page.tsx, free-session/page.tsx | Salva availability, equipment, goal, limitations, device preference | `user_state` completo (deep-merge) — può triggerare regen macrocycle |
| `DELETE /api/state` | DELETE | settings/page.tsx | "Reset to onboarding" (danger zone) | Cancella tutto — full reset |
| `POST /api/assessment/compute` | POST | settings/page.tsx | Ricalcola profilo dopo modifica inputs | `user_state.assessment.profile` |
| `POST /api/macrocycle/generate` | POST | plan/page.tsx, settings/page.tsx | "Rigenera Macrociclo" o cambio goal/equipment | `user_state.macrocycle` + tutti i `week_plans` |
| `POST /api/user/import` | POST | settings/page.tsx | Upload backup JSON | Sovrascrive intero user_state |

### Onboarding

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/onboarding/complete` | POST | onboarding/review/page.tsx | "Genera Piano" — fine wizard onboarding | Crea assessment + macrocycle da zero |
| `POST /api/onboarding/start-week` | POST | onboarding/start-week/page.tsx | Sceglie offset settimana di inizio | `user_state.macrocycle.start_date` |

### Outdoor

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/outdoor/log` | POST | outdoor/page.tsx, today/page.tsx, OutdoorLogForm | Nuova sessione outdoor | Crea log + aggiorna stats |
| `PUT /api/outdoor/log` | PUT | outdoor/page.tsx, OutdoorLogForm | Modifica sessione outdoor | Aggiorna log + stats |
| `DELETE /api/outdoor/log/{date}` | DELETE | outdoor/page.tsx | Cancella sessione outdoor | Rimuove log + stats |
| `POST /api/outdoor/spots` | POST | settings/page.tsx, quick-add-dialog.tsx | Aggiunge spot outdoor | `user_state.outdoor_spots` |
| `DELETE /api/outdoor/spots/{id}` | DELETE | settings/page.tsx | Cancella spot | `user_state.outdoor_spots` |

### Free Session

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/free-session/start` | POST | free-session/page.tsx | Sceglie superficie + modo | Crea sessione, ritorna `session_id` |
| `POST /api/free-session/{id}/log-climb` | POST | climb-logger.tsx | Logga singola salita | Aggiunge climb alla sessione in corso |
| `DELETE /api/free-session/{id}/climb/{idx}` | DELETE | climb-logger.tsx | Cancella climb loggato | Rimuove climb dalla sessione in corso |
| `POST /api/free-session/{id}/finish` | POST | free-session/page.tsx | "Fine sessione" | Finalizza sessione, calcola load_score, salva in storico |
| `DELETE /api/free-session/{id}` | DELETE | free-session/page.tsx | Annulla sessione non completata | Rimuove sessione |

### Weekly Override

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `PUT /api/weekly-override/{weekStart}` | PUT | (non ancora in UI) | Override disponibilità settimanale | `weekly_overrides[weekStart]` |
| `DELETE /api/weekly-override/{weekStart}` | DELETE | (non ancora in UI) | Rimuove override | `weekly_overrides[weekStart]` |

### Subscription

| Endpoint | Method | Componente/File | Azione utente | Cosa cambia |
|----------|--------|-----------------|---------------|-------------|
| `POST /api/subscription/checkout` | POST | subscribe/page.tsx | "Inizia prova gratuita" | Redirect Stripe — nessun cache da invalidare |
| `POST /api/subscription/portal` | POST | settings/page.tsx | "Gestisci abbonamento" | Redirect Stripe portal — nessun cache da invalidare |

---

## 3. Invalidation Matrix — la mappa principale

> **Leggenda:**  
> ✅ `setQueryData` = mutation ritorna il dato aggiornato → update cache istantaneo, no refetch  
> 🔄 `invalidateQueries` = refetch in background  
> ⚡ `invalidateQueries` (immediate) = forza refetch subito (dato critico)  
> — = nessuna azione cache necessaria

| Mutation | `['state']` | `['week', n]` | `['outdoor', ...]` | `['free-session', ...]` | Note |
|----------|-------------|---------------|---------------------|--------------------------|------|
| `POST /api/replanner/events` | — | ✅ `setQueryData(['week',n])` con `week_plan` ritornato | — | — | Ritorna `week_plan` completo |
| `POST /api/replanner/override` | — | ✅ `setQueryData(['week',n])` | — | — | Ritorna `week_plan` completo |
| `POST /api/replanner/quick-add` | — | ✅ `setQueryData(['week',n])` | — | — | Ritorna `week_plan` + `warnings[]` |
| ~~`POST /api/outdoor/convert-slot`~~ | — | — | — | — | **Nessuna invalidazione** — è una query mascherata da POST, non modifica state lato server. Verifica A187 Phase 0 |
| `POST /api/session/add-exercise` | — | ✅ `setQueryData(['week',n])` | — | — | Ritorna `week_plan` |
| `POST /api/session/remove-exercise` | — | ✅ `setQueryData(['week',n])` | — | — | Ritorna `week_plan` |
| `POST /api/feedback` | — | ⚡ `invalidateQueries(['week',n])` | — | — | **NON** ritorna week_plan. Trigga progression → cambia load next week |
| `PUT /api/state` | ✅ `setQueryData(['state'])` | 🔄 `invalidateQueries(['week',n])` | — | 🔄 `invalidateQueries(['free-session','surfaces'])` | State ritorna UserState completo. Week va aggiornato perché equipment/availability possono cambiare il piano |
| `DELETE /api/state` | ⚡ `invalidateQueries` tutte le chiavi | ⚡ tutte | ⚡ tutte | ⚡ tutte | Full reset — svuota l'intera cache |
| `POST /api/assessment/compute` | ✅ `setQueryData(['state'])` con profile aggiornato | — | — | — | Ritorna `{profile}` — merge in state cache |
| `POST /api/macrocycle/generate` | ✅ merge `setQueryData(['state'])` | ⚡ `invalidateQueries(['week', *])` | — | — | Tutti i week plan cambiano — invalida tutte le settimane |
| `POST /api/onboarding/complete` | ⚡ `invalidateQueries(['state'])` | ⚡ `invalidateQueries(['week', *])` | — | — | State completamente nuovo |
| `POST /api/onboarding/start-week` | 🔄 `invalidateQueries(['state'])` | ⚡ `invalidateQueries(['week', *])` | — | — | start_date cambia → tutti i week num cambiano |
| `POST /api/user/import` | ⚡ `invalidateQueries` tutte le chiavi | ⚡ tutte | ⚡ tutte | ⚡ tutte | Full import — svuota tutto come DELETE /state |
| `POST /api/outdoor/log` | — | — | ⚡ `invalidateQueries(['outdoor','sessions'])` + `['outdoor','stats']` + `['outdoor','log',date]` | — | Stats non tornate dalla POST |
| `PUT /api/outdoor/log` | — | — | ⚡ `invalidateQueries(['outdoor','sessions'])` + `['outdoor','stats']` + `['outdoor','log',date]` | — | Idem |
| `DELETE /api/outdoor/log/{date}` | — | — | ⚡ `invalidateQueries(['outdoor','sessions'])` + `['outdoor','stats']` + `['outdoor','log',date]` | — | Ritorna solo `{status, date}` |
| `POST /api/outdoor/spots` | — | — | ✅ `setQueryData(['outdoor','spots'])` (aggiungi spot ritornato) oppure 🔄 `invalidateQueries` | — | Ritorna `{status, spot}` — possibile setQueryData |
| `DELETE /api/outdoor/spots/{id}` | — | — | ⚡ `invalidateQueries(['outdoor','spots'])` | — | Ritorna solo `{status}` |
| `POST /api/free-session/finish` | — | — | — | ⚡ `invalidateQueries(['free-session','history',date])` | Load score e summary già nel response — niente da fare sulle altre chiavi |
| `DELETE /api/free-session/{id}` | — | — | — | ⚡ `invalidateQueries(['free-session','history',date])` | — |
| `PUT /api/weekly-override/{ws}` | — | ⚡ `invalidateQueries(['week',n])` | — | — | Override cambia il piano visualizzato |
| `DELETE /api/weekly-override/{ws}` | — | ⚡ `invalidateQueries(['week',n])` | — | — | — |
| `POST /api/subscription/checkout` | — | — | — | — | Redirect Stripe — nessuna cache |
| `POST /api/subscription/portal` | — | — | — | — | Redirect Stripe — nessuna cache |

---

## 4. Cascade Map — side effects server-side

Queste mutazioni cambiano più di quanto il nome suggerisca:

| Mutazione | Cascade server-side | Impatto cache |
|-----------|---------------------|---------------|
| `POST /api/feedback` | Triggers `progression_v1` → calcola nuovo load per sessioni future. Se è feedback su test, aggiorna `user_state.baselines` | Invalida `['week', n]` per tutte le settimane successive, non solo corrente |
| `POST /api/replanner/events` (mark_done) | Se è l'ultimo slot della settimana → backend può pre-generare week n+1 | Invalida `['week', n+1]` (precauzionale) |
| `PUT /api/state` (equipment change) | Se equipment cambia, il planner filtra sessioni diverse → week plan cambia | Invalida `['week', *]` |
| `PUT /api/state` (availability change) | Giorni disponibili cambiano → slot assignment cambia | Invalida `['week', *]` |
| `POST /api/macrocycle/generate` | Tutti i `week_plans` vengono rigenerati | Invalida `['week', *]` — **tutte** le settimane |
| `POST /api/onboarding/complete` | Crea assessment + macrocycle da zero → tutti i week freschi | Invalida tutto |
| `POST /api/outdoor/log` | Può aggiornare `user_state.outdoor_stats` internamente | `['outdoor','stats']` stale |

### Nota su `['week', n]` vs `['week', *]`

La chiave `n` è il numero settimana relativo (0 = corrente, 1 = prossima, -1 = scorsa). Dopo mutazioni che cambiano il macrocycle, **tutti** i numeri diventano stale. Strategia: usare `queryClient.invalidateQueries({ queryKey: ['week'] })` (prefix match) per invalidare tutte le settimane in un colpo.

---

## 5. Response Payload Table

| Endpoint | Ritorna | Strategia ottimale |
|----------|---------|-------------------|
| `POST /api/replanner/events` | `{week_plan: WeekPlan}` | `setQueryData(['week', n], data.week_plan)` ← **istantaneo** |
| `POST /api/replanner/override` | `{week_plan: WeekPlan}` | `setQueryData(['week', n], data.week_plan)` ← **istantaneo** |
| `POST /api/replanner/quick-add` | `{week_plan: WeekPlan, warnings: string[]}` | `setQueryData(['week', n], data.week_plan)` ← **istantaneo** |
| `POST /api/session/add-exercise` | `{week_plan: WeekPlan}` | `setQueryData(['week', n], data.week_plan)` |
| `POST /api/session/remove-exercise` | `{week_plan: WeekPlan}` | `setQueryData(['week', n], data.week_plan)` |
| `PUT /api/state` | `UserState` (full) | `setQueryData(['state'], data)` + `invalidateQueries(['week'])` |
| `POST /api/assessment/compute` | `{profile: AssessmentProfile}` | Merge in `['state']` cache: `setQueryData(['state'], old => ({...old, assessment: {...old.assessment, profile: data.profile}}))` |
| `POST /api/macrocycle/generate` | `{macrocycle: Macrocycle}` | Merge in `['state']` + `invalidateQueries(['week'])` |
| `POST /api/feedback` | `{status, limitation_suggestions?, warning?}` | Solo `invalidateQueries(['week', n])` — no setQueryData |
| `POST /api/outdoor/log` | `{status, log_path}` | `invalidateQueries(['outdoor'])` (prefix) |
| `PUT /api/outdoor/log` | `{status, load_score}` | `invalidateQueries(['outdoor'])` (prefix) |
| `DELETE /api/outdoor/log/{date}` | `{status, date}` | `invalidateQueries(['outdoor'])` (prefix) |
| `POST /api/outdoor/spots` | `{status, spot: OutdoorSpot}` | `setQueryData(['outdoor','spots'], old => [...old, data.spot])` |
| `DELETE /api/outdoor/spots/{id}` | `{status}` | `invalidateQueries(['outdoor','spots'])` |
| `POST /api/free-session/finish` | `{summary, duration_minutes, load_score}` | `invalidateQueries(['free-session','history',date])` — summary già in response |
| `DELETE /api/free-session/{id}` | `{status}` | `invalidateQueries(['free-session','history',date])` |
| `POST /api/onboarding/complete` | `{profile, macrocycle}` | `invalidateQueries()` — tutto stale |
| `POST /api/onboarding/start-week` | `{status, start_date, offset_applied}` | `invalidateQueries(['week'])` |
| `DELETE /api/state` | `{status, state: UserState}` | `queryClient.clear()` — svuota tutta la cache |
| `POST /api/user/import` | `{status}` | `queryClient.clear()` — svuota tutta la cache |
| `PUT /api/weekly-override/{ws}` | `{status, week_start, days}` | `invalidateQueries(['week', n])` |
| `DELETE /api/weekly-override/{ws}` | `{status, week_start}` | `invalidateQueries(['week', n])` |

---

## 6. Shared State — Query keys condivise tra pagine

```
['state']
  └── usato da: today, week, plan, settings, guided, start-week
  └── TUTTI devono vedere lo stesso dato fresco
  └── Una mutazione in settings → invalida ciò che today e week leggono

['week', 0]  (settimana corrente)
  └── usato da: today, week, plan
  └── Mutazione in today (mark done) → week deve aggiornare i badge
  └── Mutazione in week (replanner) → today deve vedere i nuovi slot

['outdoor', 'spots']
  └── usato da: settings, today, week, outdoor, quick-add-dialog
  └── Add/delete in settings → quick-add-dialog deve vedere spot aggiornati

['outdoor', 'sessions']
  └── usato da: today, week, outdoor
  └── Modifica in outdoor → today e week devono aggiornare badge outdoor

['free-session', 'history', date]
  └── usato da: today, week (per badge)
  └── Finish in free-session → today/week devono mostrare il badge
```

**Chiavi "globali" da invalare sempre dopo mutazioni strutturali:**
- `['state']` — qualsiasi PUT /api/state, import, reset
- `['week']` (prefix match) — qualsiasi macrocycle generate, import, reset

---

## 7. React Query Config raccomandata

### QueryClient globale (in `app/layout.tsx`)

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30s — mostra dati cached, revalida in background
      gcTime: 5 * 60_000,         // 5min — mantieni in cache dopo unmount
      retry: 1,                   // 1 retry (come attuale B155)
      refetchOnWindowFocus: false, // Evita refetch su ogni alt-tab
    },
  },
})
```

### Override per chiave specifica

```typescript
// Catalogo: praticamente immutabile
useQuery({ queryKey: ['catalog', 'sessions'], staleTime: Infinity })
useQuery({ queryKey: ['catalog', 'exercises'], staleTime: Infinity })

// Quote: cache 24h in localStorage (non React Query — vedi nota)
// staleTime: 24 * 60 * 60_000 — oppure gestione manuale localStorage

// Subscription: già pollata ogni 5min dal hook custom
useQuery({ queryKey: ['subscription', 'status'], staleTime: 5 * 60_000 })

// Week plan: dati critici — mostra subito cached, revalida
useQuery({ queryKey: ['week', n], staleTime: 60_000 })

// Outdoor stats: cambiano solo su write outdoor
useQuery({ queryKey: ['outdoor', 'stats'], staleTime: 2 * 60_000 })
```

### Pattern mutation standard

```typescript
const mutation = useMutation({
  mutationFn: (data) => postReplannerEvents(data),
  onSuccess: (responseData, variables) => {
    // Caso 1: endpoint ritorna week_plan → setQueryData istantaneo
    queryClient.setQueryData(['week', variables.weekNum], responseData.week_plan)
    
    // Caso 2: endpoint non ritorna dati aggiornati → refetch
    queryClient.invalidateQueries({ queryKey: ['week', variables.weekNum] })
  },
})
```

### Invalidazione a cascata — helper suggerito

```typescript
// Da usare dopo macrocycle generate, import, reset
function invalidateAll(queryClient: QueryClient) {
  queryClient.clear()  // oppure: invalidateQueries con prefissi specifici
}

// Da usare dopo equipment/availability change
function invalidateWeekPlans(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ['week'] })
  queryClient.invalidateQueries({ queryKey: ['state'] })
}
```

---

## 8. Priorità di implementazione per A187

| Priorità | Query Key | Perché |
|----------|-----------|--------|
| P0 | `['state']` | Fetchato su ogni navigazione — 4+ duplicati per sessione |
| P0 | `['week', n]` | Fetchato su ogni navigazione — payload pesante (ricalcolo server) |
| P1 | `['outdoor', 'sessions']` | Duplicato tra today e week — stesso fetch, stesso dato |
| P1 | `['outdoor', 'spots']` | Usato in 5 pagine, quasi immutabile |
| P2 | `['free-session', 'history', date]` | N call per N date — batch o cache separata per data |
| P2 | `['quotes', 'daily', ctx]` | localStorage manuale — 1 call/sessione invece di 1/navigazione |
| P3 | `['catalog', *]` | Immutabile — `staleTime: Infinity` elimina tutti i refetch |

---

*Audit condotto: 2026-04-07 — D176*
