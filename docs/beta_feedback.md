# Beta Feedback — climb-agent

> Ultimo aggiornamento: 2026-03-14

---

## Tester

| Nome | Data onboarding | Note |
|------|-----------------|------|
| Alexis | 2026-02-23 | Climber, allena con coach mercoledì, fa padel il lunedì |
| Davide Vato | 2026-02-23 | Feedback su edit profilo senza reset completo |
| Luca | 2026-02-23 | Feedback su minimo sessioni/settimana |
| Christie | 2026-03-07 | Main beta tester, usa loading pin (limitazione spalla) |

---

## FB-1 — Bloccare giorni per altri sport
**Da:** Alexis
**Data:** 2026-02-23
**Descrizione:** L'utente fa padel il lunedì e vorrebbe che il sistema lo sapesse per:
1. Non pianificare sessioni climbing quel giorno
2. Opzione (non obbligatoria) di ridurre l'intensità della sessione climbing il giorno dopo
**Soluzione concordata:**
- Nella disponibilità aggiungere sezione "Other activities"
- Campo testo libero per il nome dello sport (es. "Padel", "Football", "Yoga")
- Selezione giorno/i della settimana
- Toggle opzionale "Reduce climbing intensity the day after" (default OFF)
**Impatto backend:** I giorni con "other activity" sono non disponibili per climbing. Se toggle ON, il giorno dopo riceve moltiplicatore intensità ridotta.
**Priorità:** Alta
**In roadmap:** ✅ → B41
**Status:** ✅ DONE (B41 implementato: planner_v2 parse `_day_meta`, blocco giorno + riduzione intensità giorno dopo, UI in settings + onboarding)

---

## FB-2 — Sessione pianificata su giorno "non selezionato"
**Da:** Alexis
**Data:** 2026-02-23
**Chiarimento:** NON è un bug. Se l'utente chiede 4 sessioni ma ha selezionato solo 3 giorni disponibili, il sistema deve pianificare altrove. Comportamento corretto.
**Azione:** Eventualmente migliorare il testo onboarding per spiegare che target_days > giorni disponibili porta a sessioni extra su altri giorni.
**Status:** CHIUSO (comportamento corretto)

---

## FB-3 — Disponibilità settimanale variabile
**Da:** Alexis
**Data:** 2026-02-23
**Descrizione:** La disponibilità cambia settimana per settimana. L'utente vorrebbe aggiornarla facilmente ogni settimana.
**Soluzione concordata — Opzione A (reminder passivo):**
- Ogni domenica la Today view mostra un banner:
  "Next week starts tomorrow — confirm your availability"
- Bottone che apre direttamente l'editor disponibilità (già esistente in Settings)
- Zero backend: logica frontend pura (controlla se è domenica)
**Opzione B (disponibilità per settimana) scartata** — overkill, cambierebbe struttura macrociclo
**Priorità:** Media
**In roadmap:** ✅ → B42
**Status:** TODO

---

## FB-4 — Edit profilo senza reset completo
**Da:** Davide Vato
**Data:** 2026-02-23
**Descrizione:** L'utente vorrebbe poter aggiornare dati assessment (età, peso, grado massimo) senza dover fare reset completo e ripetere l'intero onboarding.
**Soluzione concordata:** Sezione "Edit profile & assessment" in Settings. Form che permette di modificare i campi principali (profilo, grades, tests) e ricalcola l'assessment senza toccare macrociclo/storico.
**Priorità:** Media
**In roadmap:** ✅ → B43
**Status:** ✅ DONE (ProfileAssessmentEditor in Settings — modifica profilo, gradi, test senza reset)

---

## FB-5 — Minimo sessioni/settimana troppo alto
**Da:** Luca
**Data:** 2026-02-23
**Descrizione:** Il sistema non permette di selezionare meno di 3 sessioni/settimana durante l'onboarding. Un atleta che si allena 1-2 volte/settimana non può usare l'app.
**Soluzione concordata:** Abbassare il minimo a 1 sessione/settimana. Il planner adatta il piano al volume disponibile.
**Priorità:** Alta
**In roadmap:** ✅ → B44
**Status:** ✅ DONE (slider min abbassato da 3 a 1 in onboarding + settings)

---

## Note generali dal primo giorno di beta

- Alexis ha fatto onboarding autonomamente ✅
- Il concetto goal + deadline è chiaro ✅
- Pain point principale: disponibilità troppo rigida per chi ha vita sportiva mista
- Feature più richiesta: gestione altri sport + blocco giorno

---

## Christie — 2026-03-07

### FB-6 — Loading pin come dispositivo primario
**Da:** Christie
**Data:** 2026-03-07
**Descrizione:** Non può usare hangboard per problemi alla spalla. Usa loading pin come dispositivo primario per finger training.
**Soluzione:** B106 (alias v1) → A120 (full LP support: 7 esercizi, baselines per-hand, device selector, guided R/L UI) → B120 (LP test sessions, past immutability).
**Status:** ✅ DONE (A120 + B120)

---

### FB-7 — "Other" per injuries
**Da:** Christie
**Data:** 2026-03-07
**Descrizione:** Lista zone infortuni mancava opzione generica.
**Soluzione:** B107 — "Other" aggiunto in onboarding + settings con notes field. Zero effetto motore.
**Status:** ✅ DONE (B107)

---

### FB-8 — Outdoor tooltip in onboarding
**Da:** Christie
**Data:** 2026-03-07
**Descrizione:** Non chiaro che i giorni outdoor si possono aggiungere dopo.
**Soluzione:** B108 — CardDescription nella pagina availability.
**Status:** ✅ DONE (B108)

---

### FB-9 — Injury-specific rehab exercises
**Da:** Christie
**Data:** 2026-03-21
**Descrizione:** When flagging an injury (e.g. finger pain, shoulder pain), the app should suggest targeted rehab/prehab exercises instead of just showing a generic warning.
**Comportamento attuale:** Generic warning message during sessions that stress the injured area.
**Comportamento desiderato:** Specific rehab exercises matched to injury type and body zone.
**Status:** Added to roadmap as Future feature. Candidate for LLM Coach (Phase 3.5).
**Roadmap ref:** "Future — Injury-Specific Rehab/Prehab" section in ROADMAP_CURRENT.md

---

### 2026-03-31 — Daniele — Guided Session: intermittent scroll + timer block (iOS PWA)

**Device:** iPhone, iOS Safari PWA
**Page:** Guided session — "Heavy Conditioning Gym" (16 exercises)
**Severity:** P3 (intermittent, self-resolving)
**Screenshots:** provided (IMG_5447.png, IMG_5448.png)

**Symptoms (both intermittent, resolved on their own):**
1. Vertical scroll blocked — content bounces back, cannot reach Done/Skip buttons
2. Timer ring unresponsive to tap — cannot start/pause timer

**Suspected causes:**
- Loading state overlay not clearing (covers scroll + timer area)
- Re-render timing issue (component re-mount places element on top temporarily)
- iOS Safari PWA touch freeze after background/foreground cycle
- CSS animation on timer ring interfering with touch events

**Reproduction:** not reliably reproducible yet. If it recurs, note:
- Does it happen immediately on page open, or after some interaction?
- Does it happen after returning from background?
- Does a pull-to-refresh or page reload fix it?

**Action:** monitor. On next frontend brief, audit guided session for:
- Any overlay/loading div with `pointer-events: auto` or high `z-index`
- Any `overflow: hidden` on parent containers that could block scroll
- Any `touch-action` CSS that could interfere with vertical scrolling
