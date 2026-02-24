# Beta Feedback — climb-agent

> Ultimo aggiornamento: 2026-02-24

---

## Tester

| Nome | Data onboarding | Note |
|------|-----------------|------|
| Alexis | 2026-02-23 | Climber, allena con coach mercoledì, fa padel il lunedì |
| Davide Vato | 2026-02-23 | Feedback su edit profilo senza reset completo |
| Luca | 2026-02-23 | Feedback su minimo sessioni/settimana |

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
