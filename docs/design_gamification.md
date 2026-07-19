# Design Gamification — climb-agent (A-GAMIFY-00)

> **Status:** DRAFT v1 — in attesa di approvazione Daniele
> **Date:** 2026-07-19
> **Type:** Design audit (prerequisito di tutti gli A-GAMIFY-*)
> **Filosofia guida:** "Train better, not more" (D79) + Self-Determination Theory (D77)

---

## 1. Principio fondante

climb-agent è un'app di **allenamento periodizzato**, non un habit tracker. La gamification di un'app di training ha un vincolo che Duolingo e Strava non hanno: **il comportamento ottimale include NON allenarsi** (rest day, deload, taper). Qualsiasi meccanica che premia "di più" spinge l'utente contro il suo stesso piano.

Da qui il principio che governa ogni proposta:

> **Premiamo la qualità dell'adesione al piano — incluso il riposo — mai la quantità di attività.**

## 2. Evidenze dalla ricerca (2026-07-19)

### 2.1 Anti-pattern documentati

| Pattern | Evidenza | Perché lo escludiamo |
|---|---|---|
| **Daily streak (Duolingo)** | Loss aversion → ansia, colpa, "engagement built on fear". Notifiche shaming ("You made Duo sad") sono le più efficaci proprio perché colpevolizzano | Viola il vincolo hard §3. Un giorno di riposo rotto-streak = punire il comportamento corretto |
| **Ring giornalieri (Apple Watch)** | Richieste utenti inevase di "rest day"; gente che si allena malata per chiudere i ring; reset giornaliero = zero visione di trend | Il nostro ciclo è settimanale/di fase, non giornaliero |
| **Confronto sociale (Strava)** | Ricerca: social comparison dannosa soprattutto per utenti a bassa self-compassion (in particolare donne); "if it's not on Strava it didn't happen"; segments/kudos → pressione a performare sempre | Ego orientation < mastery orientation (KB Topic 09). Siamo single-player by design |
| **Scorecard/ranking (8a.nu)** | Grade chasing, ego attaccato ai gradi, community ambivalente. La ricerca climbing conferma: task/mastery orientation → comportamenti più adattivi di ego orientation | Il grado arriva come conseguenza del processo. Non classifichiamo persone |
| **Troppa gamification** | Studio 2025 (Frontiers, S-shaped richness): gruppo con gamification MEDIA fa +38% attività vs bassa e +19% vs ALTA. Più feature ≠ più engagement | Poche meccaniche, ben fatte. No punti/XP/livelli/valute |

### 2.2 Modelli positivi

| Modello | Cosa fa bene | Cosa ne prendiamo |
|---|---|---|
| **Whoop** | Premia il recovery (recovery verde, sleep performance), non l'attività. Amato dagli atleti proprio perché "non celebra step count" | Il riposo rispettato è un risultato di prima classe, con colore/celebrazione positiva |
| **Finch** | "Gentle gamification": mai punire un giorno mancato, tono compassionevole, care-framing. Retention alta senza shame | Nessuna meccanica ha uno stato di "fallimento". Skip = neutro, mai rosso |
| **Garmin badges** | ~200 badge one-time semplici, riconoscimento istantaneo, zero pressione. Molto amati | Milestone una tantum, unlock immediato al verificarsi dell'evento |
| **Ricerca milestone** | Retention correlata alla DIFFICOLTÀ dell'achievement: 74% retention per i più difficili vs 32% per i banali | Poche milestone facili di attivazione + milestone "vere" legate a traguardi reali di training |
| **Competitor climbing** | Crimpd/KilterBoard/TopLogger: gamification assente o solo leaderboard di contest | **White space**: nessuna app climbing premia il riposo e il processo. Differenziatore |

## 3. Regole non negoziabili

**Metriche che premiamo:**
1. Completamento di fase e di macrociclo (competence, SDT)
2. Milestone una tantum ("prima volta che...")
3. Rest day e deload **rispettati** (aderenza al piano, incluso il non-fare)
4. Qualità del processo (feedback dato, test completati, settimana aderente al piano)

**Metriche che NON premiamo MAI:**
1. Giorni consecutivi di attività (streak giornalieri)
2. Volume cumulativo ("100 sessioni questo mese")
3. RPE alto / "hai spinto forte"
4. Confronto con altri utenti (leaderboard, ranking, kudos)
5. Sessioni extra non pianificate

**Vincoli hard:**
- Nessun elemento può indurre senso di colpa per un giorno saltato o un rest day. Skip = **colore neutro sempre**, nessun "broken", nessun reset visibile.
- Nessuna meccanica ha uno stato negativo persistente: si può solo guadagnare, mai perdere.
- Nessuna notifica push a scopo gamification (niente "il tuo streak sta per scadere").
- Tutto deterministico e derivato da dati già esistenti (feedback log, week plans, outdoor log). Nessun modulo high-risk toccato (planner/replanner/macrocycle/resolver/progression/closed-loop).
- Opt-out: una preferenza `preferences.gamification_enabled` (default true) spegne tutto.

## 4. Linee guida copy

Tono SDT: autonomia (mai ordini), competenza (progresso concreto), relatedness (parte di un percorso). Sempre "train better, not more".

| ❌ Mai | ✅ Sì |
|---|---|
| "Don't break your streak!" | "Strength & Power phase complete — your fingers got a real stimulus block. 💪" |
| "You missed 2 sessions this week 😢" | "You adapted your week and kept the key sessions. That's how real training works." |
| "You're on fire! 5 days in a row!" | "Rest day respected. Recovery is where the gains happen." |
| "Top 10% of users!" | "First outdoor session of your cycle logged." |
| "Come back or you'll lose your progress" | (nessuna notifica — il progresso non si perde) |

## 5. Proposte

### P1 — Macrocycle progress + phase completion (= A-GAMIFY-01) ⭐ consigliata per prima

Il progresso nel macrociclo come elemento centrale di gratificazione (competence, SDT).
- `MacrocycleProgressBar` su `/plan`: 5 fasi, % completata, marker settimana corrente.
- **Celebrazione di transizione fase**: toast/modal al primo accesso nella nuova fase ("Base complete — 4 weeks of aerobic foundation in the bank. Now we build strength."), con 1 riga educational su cosa aspettarsi (riusa i testi "About this phase").
- Flag `phase_completion_seen[]` in user_state; snapshot in `completed_macrocycles[]` su start-new-cycle (già esiste da A-NEW-MACRO).
- **Effort M** | frontend + light backend | zero moduli high-risk.

### P2 — Monthly heatmap "rest-positive" (= A-GAMIFY-03)

Calendario mensile in fondo a `/reports/weekly`.
- Verde (3 intensità via load) = sessione completata; **verde tenue distinto = rest day rispettato** (il tratto differenziante: premiamo il riposo); grigio = nessuna programmazione; **neutro = skipped (NO color shame)**.
- Tap sulla cella → day view.
- Solo lettura da dati esistenti, zero backend nuovo.
- **Effort S** | frontend-only.

### P3 — Milestone system (= A-GAMIFY-02)

Eventi una tantum, unlock istantaneo (modello Garmin), append-only (mai revocati).
- Catalog `backend/catalog/milestones/v1/milestones.json`, ~15-20 iniziali su 4 categorie: grade firsts (primo 6b/7a/... redpoint/onsight — dai log esistenti), session firsts (prima outdoor, prima guided, prima custom, prima free), macrocycle (primo test di ogni tipo, prima fase performance, primo ciclo completato), **process firsts** (primo deload completato integralmente, primo retest con miglioramento, prima settimana 100% aderente incluso il riposo).
- Distribuzione di difficoltà deliberata (ricerca: gli achievement difficili trattengono di più): 1/3 facili-attivazione, 1/3 medi, 1/3 “career milestones”.
- Toast celebrativo + galleria `/milestones` (o sezione in `/plan`).
- **Effort M** | catalog + hook su feedback/outdoor log + frontend.

### P4 — "Smart Week" recognition settimanale (evoluzione di A-GAMIFY-04, opzionale, ULTIMA)

Sostituisce il concetto di streak con una cadenza **settimanale**: la weekly check-in card riconosce una "smart week" = sessioni chiave fatte (anche se spostate) + rest days rispettati + feedback dato. Nessun contatore di settimane consecutive — ogni settimana si valuta da sola.
- **Rischio percezione-pressione** (lo segnala la stessa roadmap): da fare SOLO dopo P1-P3, se il feedback utenti è positivo.
- **Effort M** | riusa `report_engine`.

### P5 — Micro-copy "recovery respected" (nuova, dalla ricerca Whoop/Finch) — quick win

Non una meccanica: quando un rest day pianificato passa senza sessioni extra, o un deload si chiude, la Today/report card mostra una riga positiva ("Rest day respected — recovery is where the gains happen"). Zero stato, zero badge, pura affermazione del comportamento corretto.
- **Effort XS** | copy + condizione frontend. Imbarcabile dentro P1.

### P6 — Year/cycle recap (nuova, candidata futura)

Recap di fine macrociclo (e annuale): sessioni, fasi completate, progressione carichi, grade progression, spot visitati — riflessivo e mastery-framed, niente confronto. Il "recap" è l'unico formato Strava universalmente amato. Si collega all'esistente "Annual report" in roadmap. **Post P1-P3.**

### Esplicitamente escluse
Leaderboard/confronto sociale · streak giornalieri · punti/XP/livelli/valute · badge di volume · notifiche push di gamification · pet/mascotte (il care-framing di Finch funziona ma è fuori tono per il prodotto).

## 6. Sequenza consigliata

1. **P1** (M) — massimo valore/rischio minimo, cuore SDT-competence *(+ P5 embedded, XS)*
2. **P2** (S) — heatmap rest-positive, differenziatore visivo immediato
3. **P3** (M) — milestone system
4. **P6** (M) — recap di fine ciclo, quando i primi utenti chiudono un macrociclo
5. **P4** (M) — solo se P1-P3 ricevono feedback positivo; si scarta senza rimpianti

Effort totale P1+P2+P3: ~4-5 giorni. Ogni proposta è un brief A indipendente con branch + preview (tutte toccano frontend).

## 7. Fonti

- [Frontiers 2025 — S-shaped impact of gamification feature richness on exercise adherence](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1671543/full)
- [Motivation crowding effects in gamified fitness apps (mixed-methods)](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2023.1286463/full)
- [Gamification-induced feelings & continued mHealth use (SDT, SEM)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8391751/)
- [The Duolingo Owl, Dark Patterns, and Digital Guilt](https://opinionsandconditions.substack.com/p/duolingo-owl-dark-patterns-digital-guilt)
- [Duolingo streaks & loss aversion](https://screenwiseapp.com/guides/duolingo-streaks-and-anxiety-in-kids)
- [Apple Watch rings: richiesta rest/sick days](https://discussions.apple.com/thread/254404555) · [Analisi oltre i ring](https://fitnesswrapped.com/guides/how-to-analyze-apple-watch-workouts)
- ["Strava made me do it": social comparison & self-surveillance](https://www.researchgate.net/publication/400287585_Strava_made_me_do_it_Psychological_effects_of_social_comparison_and_self-surveillance_on_a_social_network_for_athletes) · ["If It's not on Strava it Didn't Happen"](https://www.researchgate.net/publication/366679956_If_It's_not_on_Strava_it_Didn't_Happen_Perceived_Psychosocial_Implications_of_Strava_use_in_Collegiate_Club_Runners)
- [WHOOP recovery-first design](https://www.925studios.co/blog/whoop-design-breakdown) · [WHOOP Recovery 101](https://www.whoop.com/us/en/thelocker/how-does-whoop-recovery-work-101/)
- [Finch: gentle gamification senza streak-shame](https://screensdesign.com/showcase/finch-self-care-pet) · [Finch UX teardown](https://medium.com/@deepthi.aipm/ux-teardown-finch-self-care-app-18122357fae7)
- [Garmin badges: design spotlight](https://medium.com/@pancakefeed/project-spotlight-badges-320aa50375f4)
- [Streaks vs milestones & difficoltà achievement → retention](https://trophy.so/blog/achievements-feature-gamification-examples) · [Streaks case study](https://trophy.so/blog/streaks-gamification-case-study)
- [The Problem With Personal Grades (Evening Sends)](https://eveningsends.com/the-problem-with-personal-grades/) · [Egos & Route Grades (Climbing)](https://www.climbing.com/skills/egos-route-grades-everyone-loses/?scope=anon)
- Interno: `docs/research_kb/09_climbing_philosophy_motivation.md` (SDT, mastery vs ego orientation, process goals), decisioni D77/D79.
