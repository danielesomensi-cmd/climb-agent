# D175 — Frontend Performance Audit: Page Navigation Latency

**Data:** 2026-04-07 | **Tipo:** D (read-only audit) | **Stato:** ✅ Done

---

## Sintesi esecutiva

Ogni navigazione tra le pagine principali (today/week/plan/settings) ri-fetcha l'intera user_state da zero — nessun layer di caching client-side esiste. Il collo di bottiglia principale è la mancanza di un global state condiviso che persista tra le navigazioni. Soluzione raccomandata: **React Query** (TanStack Query).

---

## 1. API calls per pagina

### `/today` — `app/(main)/today/page.tsx`

| Endpoint | Metodo | Al mount? | Parallel? |
|----------|--------|-----------|-----------|
| `/api/week/0` | GET | ✅ sì | `Promise.all` ✅ |
| `/api/state` | GET | ✅ sì | `Promise.all` ✅ |
| `/api/quotes/daily?context=…` | GET | lazy (dopo weekPlan) | singolo |
| `/api/outdoor/sessions?from=…` | GET | condizionale | singolo |
| `/api/free-session/history?date=D` | GET | condizionale | Promise.all per ogni data (N call) |
| `/api/subscription/status` | GET | sì (hook poll) | singolo |

**Note:** le due call principali sono parallele ✅. Il problema è che ripartono da zero ad ogni mount.

---

### `/week` — `app/(main)/week/page.tsx`

| Endpoint | Metodo | Al mount? | Parallel? |
|----------|--------|-----------|-----------|
| `/api/week/0` | GET | ✅ sì | `Promise.all` ✅ |
| `/api/state` | GET | ✅ sì | `Promise.all` ✅ |
| `/api/outdoor/sessions?from=…` | GET | condizionale | singolo |
| `/api/free-session/history?date=D` | GET | condizionale | Promise.all per ogni data (N call) |

**Note:** stesso pattern di `/today`. Cambio settimana → ri-fetcha `/api/week/{n}` intero (include ricalcolo server-side).

---

### `/plan` — `app/(main)/plan/page.tsx`

| Endpoint | Metodo | Al mount? | Parallel? |
|----------|--------|-----------|-----------|
| `/api/state` | GET | ✅ sì (via `useUserState`) | singolo |
| `/api/state/status` | GET | ✅ sì (stale check) | singolo |

**Note:** due call sequenziali, entrambe su `/api/state*`. Il payload macrocycle è incluso in `/api/state`.

---

### `/settings` — `app/(main)/settings/page.tsx`

| Endpoint | Metodo | Al mount? | Parallel? |
|----------|--------|-----------|-----------|
| `/api/state` | GET | ✅ sì (via `useUserState`) | singolo |
| `/api/outdoor/spots` | GET | lazy (useEffect separato) | singolo |

**Note:** le due call sono sequenziali (effetti separati). Ogni mutazione (save equipment, save goal…) chiama `refresh()` → nuovo `GET /api/state`.

---

### `/free-session` — `app/(main)/free-session/page.tsx`

| Endpoint | Metodo | Al mount? | Parallel? |
|----------|--------|-----------|-----------|
| `/api/free-session/surfaces` | GET | ✅ sì | singolo |

**Note:** pagina veloce perché fetcha solo i dati strettamente necessari (superfici/palestre). Non fetcha `/api/state` né `/api/week`. Questo è il pattern da replicare.

---

## 2. Caching — stato attuale

| Layer | Presente? | Note |
|-------|-----------|------|
| React Query / SWR | ❌ No | Assente |
| Zustand / Jotai / Context globale | ❌ No | Solo Clerk auth context |
| Cache in-memory cross-navigation | ❌ No | `useState` locale, azzerato ad ogni unmount |
| localStorage | Parziale | Solo: guided session feedback + free session draft |
| sessionStorage | Parziale | Solo: wizard onboarding |
| HTTP cache / Next.js route cache | Non applicabile | Chiamate autenticate con token Clerk, no cache pubblica |
| Poll subscription | ✅ Sì | `useSubscription` ogni 5 min |

**Conclusione:** ogni navigazione è una cold start completa.

---

## 3. Analisi stack

```
fetch() nativo
  → request() wrapper in api.ts
      → getAuthHeaders() → Clerk.getToken()
          → API backend (Railway, ~200-400ms RTT)
```

- **Nessun caching**: ogni `request()` è una nuova fetch HTTP
- **Retry B155**: se Clerk restituisce 401, attende 500ms e riprova → +500ms latency sulle navigazioni veloci
- **Parallelismo parziale**: today/week usano `Promise.all` per le 2 call principali ✅, ma le call secondarie sono sequenziali

---

## 4. Bottleneck ranking

| # | Problema | Impatto | Pagine |
|---|---------|---------|--------|
| 1 | `GET /api/state` ri-fetchato ad ogni navigazione | 🔴 Critico | today, week, plan, settings |
| 2 | `GET /api/week/0` ri-fetchato ad ogni navigazione | 🔴 Critico | today, week |
| 3 | Free session history: N call separate per N date | 🟠 Alto | today, week |
| 4 | Outdoor sessions fetchato indipendentemente in ogni pagina | 🟠 Alto | today, week |
| 5 | `GET /api/state` chiamato più volte per ogni mutazione in settings | 🟡 Medio | settings |
| 6 | Quote fetchata on-demand senza caching 24h | 🟡 Medio | today |
| 7 | Clerk retry +500ms su navigazione veloce | 🟡 Medio | tutte |
| 8 | `GET /api/state/status` sequenziale a `/api/state` in plan | 🟡 Basso | plan |

---

## 5. Strategia cache raccomandata per endpoint

| Endpoint | Cambia quando? | Strategia | staleTime | gcTime |
|----------|---------------|-----------|-----------|--------|
| `GET /api/state` | Ogni mutazione (PUT /api/state, feedback, replanner) | `staleWhileRevalidate` + invalidate on write | 30s | 5min |
| `GET /api/week/{n}` | Regen macrocycle, feedback, replanner override | `staleWhileRevalidate` + invalidate on write | 60s | 5min |
| `GET /api/state/status` | Stesso di `/api/state` | Deduplicato via React Query | 30s | 2min |
| `GET /api/outdoor/sessions` | POST/PUT/DELETE outdoor | Cache + invalidate on write | 60s | 5min |
| `GET /api/free-session/history?date=D` | POST finish/delete | Cache per data + invalidate | 60s | 5min |
| `GET /api/outdoor/spots` | POST/DELETE spots | Cache + invalidate on write | 5min | 10min |
| `GET /api/quotes/daily?context=C` | Mai (statico per fase) | localStorage 24h (no network) | — | — |
| `GET /api/subscription/status` | Evento Stripe webhook | 5min poll → già ok | 5min | 10min |
| `GET /api/free-session/surfaces` | Aggiunta palestre | Cache lunga | 5min | 15min |

---

## 6. Libreria raccomandata: React Query (TanStack Query)

**Motivazione vs SWR:**

| Criterio | React Query | SWR |
|---------|------------|-----|
| Cache invalidation manuale | ✅ `invalidateQueries()` | ⚠️ Limitato |
| Deduplica richieste identiche | ✅ Automatica | ✅ Automatica |
| Ottimistic updates | ✅ Built-in | ⚠️ Manuale |
| Background refetch | ✅ | ✅ |
| DevTools | ✅ React Query DevTools | ⚠️ Limitato |
| Configurazione globale | ✅ `QueryClient` | ⚠️ Limitato |
| Integrazione mutation + invalidate | ✅ `useMutation` + `onSuccess` | ⚠️ Manuale |

React Query è la scelta corretta perché le mutazioni (feedback, replanner, settings save) devono invalidare cache specifiche — scenario in cui React Query eccelle rispetto a SWR.

---

## 7. Quick wins (senza React Query)

Questi miglioramenti sono implementabili **adesso** senza cambiare l'architettura:

| Win | Dove | Sforzo | Impatto |
|----|------|--------|---------|
| Parallelizzare `GET /api/state` + `GET /api/state/status` in plan | `plan/page.tsx` | XS | Elimina 1 roundtrip sequenziale |
| Parallelizzare `GET /api/state` + `GET /api/outdoor/spots` in settings | `settings/page.tsx` | XS | -200ms su settings |
| Cache quote in localStorage (chiave: `quote_{context}_{date}`) | `today/page.tsx` | S | Elimina 1 call per sessione |
| Endpoint `GET /api/free-session/history?from=D1&to=D2` (range) | backend + frontend | M | 7 call → 1 call |

---

## 8. Piano implementazione (brief successivo)

L'implementazione React Query è un brief A (feature), dimensione M/L. Passi:

1. `npm install @tanstack/react-query`
2. `QueryClientProvider` in `app/layout.tsx` con config globale
3. Migrare `useUserState` → `useQuery({ queryKey: ['state'], ... })`
4. Migrare `getWeek(n)` → `useQuery({ queryKey: ['week', n], ... })`
5. In ogni mutazione (feedback, replanner, PUT state): `queryClient.invalidateQueries(['state'])` / `['week', n]`
6. Test: verificare che navigazione today→week→plan non trigga nuove fetch (solo background revalidation)

**Stima:** ~4-6h. Rischio: medio (tocca ogni pagina principale).

---

## 9. Risposta alla domanda "perché free-session è veloce?"

`/free-session` carica solo `GET /api/free-session/surfaces` (lista palestre, payload piccolo). Non fetcha `/api/state` né `/api/week`. È il pattern corretto: **fetch only what you need**. Le pagine today/week/plan fetchano l'intera user_state anche se ne usano solo una parte.

---

*Audit condotto: 2026-04-07 — D175*
