# climb-agent — Design: Goal → Macrociclo → Sessione

> Documento di design per il sistema di periodizzazione adattiva.  
> Versione: 1.1 — febbraio 2026  
> Stato: approvato in discussione, pronto per implementazione

---

## 1. Principio guida

Il sistema deve rispondere a una domanda: **"Dato il mio goal, i miei punti deboli, e quanto tempo ho, cosa devo fare oggi?"**

Il flusso è:
```
Assessment → Goal → Macrociclo → Settimana → Sessione → Feedback → Adattamento
```

---

## 2. Assessment: trovare i punti deboli

### 2.1 Perché è fondamentale

Il primo passo non è allenarsi, ma capire dove sei debole. Due 
climber che vogliono entrambi fare 8b possono aver bisogno di 
programmi completamente diversi:

- Climber A: forte di dita, debole in PE e tecnica → più volume
  in parete, 4x4, tattica di via
- Climber B: buona tecnica, dita deboli → più hangboard, max hang,
  forza generale

Il profilo debolezze guida TUTTO: distribuzione delle sessioni,
pesi per fase, priorità degli esercizi.

### 2.2 Le 6 dimensioni da valutare

| Dimensione | Come si misura | Benchmark (per 7c+ lead) |
|-----------|---------------|-------------------------|
| **Forza dita max** | Max hang 20mm 5s (kg totali / BW) | ≥ 1.3x BW |
| **Resistenza dita** | Repeaters 7:3 x6 su 20mm, o Critical Force | CF/BW ≥ 0.55 |
| **Forza trazione** | Weighted pullup 1RM (kg totali / BW) | ≥ 1.5x BW |
| **Power endurance** | 4x4 bouldering (n° problemi completati), o tempo su via continua | Soggettivo + grado |
| **Tecnica/Tattica** | Grado onsight vs grado progetto (gap) | Gap ≤ 2 gradi |
| **Composizione corporea** | BW, body fat %, rapporto forza/peso | Individuale |

### 2.3 Come funziona nel sistema

**Onboarding (prima volta):**

Il sistema fa domande mirate per costruire il profilo iniziale:

1. Dati fisici: peso, altezza, body fat (se noto)
2. Livello attuale: grado max boulder, grado max lead (RP e OS)
3. Esperienza: anni di arrampicata, anni di training strutturato
4. Test fisici (opzionali ma consigliati):
   - Max hang 20mm 5s: carico totale
   - Weighted pullup 1RM
   - Trazioni max a corpo libero
5. Autovalutazione punti deboli:
   - "Dove senti di perdere di più sulle vie?"
   - Opzioni: pompo troppo presto / non reggo i movimenti duri /
     non leggo bene la via / cado per errori tecnici / le dita
     cedono / non gestisco il riposo in via
6. Attrezzatura e disponibilità (già presente nel sistema)

**Assessment periodico (ogni 6 settimane):**

Mini-test integrati nelle sessioni normali, non giornate dedicate:
- Sessione test max hang (già presente: `test_max_hang_5s`)
- Sessione test PE (da creare)
- Review dei gradi scalati (indoor + outdoor) dal log

### 2.4 Profilo debolezze → Pesi del macrociclo

L'assessment produce un **profilo a radar** con 6 assi normalizzati
(0-100) rispetto al livello target. Da questo si derivano i pesi
per il macrociclo:

```
Esempio: goal 8b lead, attuale 7c

Forza dita:    82/100  → punto forte  → mantenimento
Trazione:      78/100  → punto forte  → mantenimento
PE:            45/100  → punto debole → priorità alta
Tecnica:       50/100  → punto debole → priorità alta
Endurance:     55/100  → medio        → sviluppo moderato
Composizione:  70/100  → ok           → monitoraggio
```

Questi pesi influenzano la distribuzione delle sessioni in ogni fase.

---

## 3. Goal

### 3.1 Struttura del goal

```json
{
  "goal_type": "lead_grade",
  "discipline": "lead",
  "target_grade": "8b",
  "target_style": "redpoint",
  "current_grade": "7c",
  "deadline": "2026-06-30",
  "override_mode": null
}
```

### 3.2 Tipi di goal

| goal_type | Discipline | Stato | Note |
|-----------|-----------|-------|------|
| `lead_grade` | Lead/Sport | **v1** | Primo da implementare |
| `boulder_grade` | Boulder | futuro | Macrociclo power-heavy |
| `all_round` | Misto | futuro | Bilanciato |
| `outdoor_season` | Misto | futuro | Peak per date specifiche |
| `maintenance` | Qualsiasi | futuro | Mantenimento, basso volume |

### 3.3 Override manuale

L'utente può in qualsiasi momento:
- Cambiare goal → rigenera macrociclo
- Forzare una fase → "vai al peak, ho un trip tra 2 settimane"
- Forzare una settimana → "questa settimana solo climbing"
- Forzare una sessione → day override (già funzionante)

---

## 4. Macrociclo: periodizzazione Hörst adattiva + DUP

### 4.1 Il modello base (Hörst 4-3-2-1 adattato)

Ciclo di 10-13 settimane (configurabile) che allena i 3 sistemi 
energetici in sequenza, con training concurrent dentro ogni fase:

| Fase | Settimane base | Energia primaria | Focus lead |
|------|---------------|-----------------|------------|
| **Endurance Base** | 3-4 | Aerobica | Volume climbing, ARC, base aerobica, tecnica |
| **Strength & Power** | 2-3 | Anaerobica alattacida | Max hang, forza generale, limit boulder |
| **Power Endurance** | 2-3 | Anaerobica lattacida | 4x4, interval climbing, vie lunghe |
| **Performance** | 1-2 | Specifica | Climbing al limite, progetto vie, outdoor |
| **Deload** | 1 | Recupero | Volume bassissimo, mobilità, riposo attivo |

### 4.2 Concurrent training (DUP)

Anche durante una fase, non si fa SOLO quel tipo di lavoro. Ogni 
settimana ha un po' di tutto, ma i pesi cambiano per fase.

Esempio: settimana tipo in fase "Power Endurance":

```
Lun pranzo:  Core + prehab spalla (breve, 30min)
Lun sera:    4x4 bouldering + PE intervals (palestra, 1.5h)
Mar pranzo:  Hangboard mantenimento (breve, 30min)  
Mar sera:    Tecnica lead + volume moderato (palestra, 1.5h)
Mer:         Riposo completo
Gio pranzo:  Forza generale breve (antagonisti, 30min)
Gio sera:    Power endurance vie (palestra o trav, 1.5h)
Ven pranzo:  Mobilità + prehab (breve, 30min)
Ven sera:    Volume climbing facile + tattica (palestra, 1.5h)
Sab:         Outdoor (se bel tempo) o sessione lunga palestra
Dom:         Riposo
```

### 4.3 Distribuzione per fase (lead focus, PE come punto debole)

| Dominio | Base | S&P | PE | Perf | Deload |
|---------|------|-----|-----|------|--------|
| Forza dita | 20% | 35% | 15% | 10% | 5% |
| Trazione/Forza gen. | 15% | 25% | 10% | 5% | 5% |
| Power endurance | 15% | 10% | 35% | 20% | 5% |
| Volume climbing | 25% | 10% | 15% | 25% | 10% |
| Tecnica/Tattica | 20% | 10% | 15% | 25% | 5% |
| Core/Prehab | 5% | 10% | 10% | 15% | 10% |

NB: Questi pesi si personalizzano in base al profilo debolezze.

### 4.4 Adattività: come le fasi si allungano/accorciano

**Readiness to advance (pronto per la fase successiva?):**
- Feedback sugli esercizi focus sono stabili "ok"/"easy" per 2+ 
  settimane → avanza
- Feedback ancora "hard" → estendi fase di 1 settimana (max +2)

**Overreach (stai esagerando?):**
- Fatigue proxy sopra soglia per 5+ giorni
- Feedback "very_hard" ripetuti + pain flags
- → Mini-deload (3-5 giorni) e rallenta progressione

**Plateau (non migliori?):**
- Working loads fermi per 3+ settimane
- → Suggerisci cambio stimolo o assessment

---

## 5. Deload (modello misto)

1. **Programmato**: settimana deload alla fine di ogni macrociclo
2. **Adattivo**: se fatigue proxy supera la soglia, 3-5 giorni di
   deload dentro la fase corrente
3. **Pre-trip**: se l'utente ha un trip outdoor, scala il volume
   nei 4-5 giorni prima automaticamente

Settimana deload: volume -50%, nessun esercizio "max"/"high",
2-3 sessioni, focus mobilità + tecnica facile + prehab.

---

## 6. Budget settimanale e slot

### 6.1 Tipologie di slot

| Slot | Durata | Cosa ci sta |
|------|--------|------------|
| **Sera (lungo)** | 1.5-2h | Sessione completa: warmup + main + accessori + cooldown |
| **Pranzo (breve)** | 30-45min | Hangboard, core, prehab, tecnica specifica |
| **Weekend (variabile)** | 2-4h | Outdoor, sessione lunga palestra, climbing volume |

### 6.2 Come il macrociclo riempie gli slot

Il planner assegna le sessioni in base a:
1. Fase corrente del macrociclo (pesi)
2. Profilo debolezze (priorità)
3. Slot disponibili (sera vs pranzo vs weekend)
4. Vincoli hard (no finger consecutivi, recovery dopo hard day)
5. Outdoor programmato/spontaneo

---

## 7. Outdoor nel piano

### 7.1 Outdoor spontaneo (weekend)

L'utente segna "domani vado fuori" → il sistema:
- Elimina la sessione pianificata
- Adatta il giorno dopo (recovery se intenso)
- Dopo l'uscita, l'utente logga cosa ha scalato

### 7.2 Trip programmati

- Trip breve (weekend): nessun adattamento macro, solo day override
- Trip lungo (3+ giorni): deload pre-trip + recovery post-trip

### 7.3 Logging outdoor

```json
{
  "date": "2026-03-15",
  "type": "outdoor_session",
  "location": "Arco",
  "discipline": "lead",
  "climbs": [
    {"name": "Nuvole bianche", "grade": "7b+", "style": "redpoint", 
     "attempts": 3, "notes": "Crux a metà via, pompa finale"},
    {"name": "Via degli amici", "grade": "6c+", "style": "onsight", 
     "attempts": 1}
  ],
  "overall_feel": "good",
  "fatigue": "medium",
  "conditions": "sole, 15°C, roccia asciutta"
}
```

---

## 8. Feedback granulare: piano vs realtà

### 8.1 Il principio

Ogni sessione ha un piano (cosa il sistema ti dice di fare) e un
risultato (cosa hai fatto davvero). L'utente registra la differenza.

### 8.2 Flusso nella day view

```
SESSIONE PIANIFICATA:              COSA HAI FATTO:
├── Warmup                         ├── Fatto ✓
├── 3x vie 7a (20 min)            ├── 2x 7a ✓ + 1x 6c (stanco)
├── 4x4 boulder V4 (25 min)       ├── 3 round ok, 4° fallito
├── Core 3x12                      ├── Fatto, easy
└── Cooldown                       └── Fatto ✓

Feedback generale: "ok, un po' stanco"
Citazione del giorno: "..."
```

### 8.3 Cosa si registra per ogni esercizio

**Esercizi con carico (hangboard, weighted pullup, ecc.):**
- Carico usato (kg)
- Serie x ripetizioni completate
- Feedback: very_easy / easy / ok / hard / very_hard

**Esercizi di climbing (vie, boulder):**
- Gradi effettivamente scalati (lista)
- Stile: onsight / flash / redpoint / progetto / repeat
- Completati vs non completati
- Note libere

**Esercizi generici (core, prehab, mobilità):**
- Fatto / non fatto
- Feedback: easy / ok / hard

Questo vale sia indoor che outdoor — stessa interfaccia, stessi
dati. L'outdoor aggiunge location e condizioni.

---

## 9. Citazioni motivazionali

Catalogo JSON di citazioni, tag per contesto:

```json
{
  "id": "q001",
  "text": "The best climber is the one having the most fun.",
  "author": "Alex Lowe",
  "tags": ["motivation", "mindset"],
  "source": "climber"
}
```

Categorie di source: `climber`, `athlete`, `personal` (aggiunte 
dall'utente).

Selezione: 1 citazione per sessione, scelta per contesto 
(hard day → perseveranza, deload → pazienza) con rotazione 30 giorni.

---

## 10. Tracking storico e report

### 10.1 Cosa si traccia

Ogni allenamento (indoor e outdoor) viene loggato nel sistema 
append-only esistente (JSONL).

### 10.2 Report

**Settimanale:**
- Sessioni completate vs pianificate (aderenza %)
- Volume totale (ore, n° sessioni)
- Highlight: grado max, PR carichi

**Mensile:**
- Trend carichi (max hang, weighted pullup)
- Distribuzione gradi scalati (indoor + outdoor)
- Aderenza al piano
- Fase macrociclo e avanzamento
- Suggerimenti per il mese successivo

**Annuale:**
- Tutti i gradi scalati (timeline + distribuzione)
- Progressione nel tempo (grafico)
- Volume totale
- Infortuni/pause
- Confronto con obiettivi

---

## 11. LLM Coach: layer conversazionale

### 11.1 Principio architetturale

L'engine resta **100% deterministico e rule-based** — zero LLM nel
loop decisionale. L'LLM (Claude Sonnet) è un layer conversazionale
SOPRA il motore: suggerisce, spiega, analizza, ma non modifica
direttamente piani o stato. Ogni azione concreta passa dall'engine.

```
Utente ↔ LLM Coach ↔ API Backend ↔ Engine deterministico
              ↑
     Riceve in context:
     - user_state (profilo, assessment, goal)
     - piano corrente (macrociclo, settimana, sessione di oggi)
     - log recenti (ultime 2 settimane)
     - citazioni disponibili
```

### 11.2 Casi d'uso

**Onboarding guidato:**
L'LLM conduce l'assessment iniziale come una conversazione naturale
con un coach, non un form. Raccoglie le risposte e le struttura
per l'engine.

**Coaching pre-sessione:**
"Oggi mi sento stanco" → l'LLM vede fatigue_proxy, piano di oggi,
feedback recenti → suggerisce: "scala l'intensità" o "fai recovery"

**Analisi post-sessione:**
"Come è andata?" → l'utente racconta a parole → l'LLM compila il
feedback strutturato (gradi fatti, RPE, note) per il sistema

**Discussione climbing:**
"Vado ad Arco settimana prossima, come mi preparo?" → l'LLM conosce
il piano, il livello, le debolezze → suggerisce adattamenti

**Citazioni e motivazione:**
Contestuali alla sessione, alla fase, al mood dell'utente

### 11.3 Implementazione tecnica

- **Modello**: Claude Sonnet (costo basso, velocità buona)
- **API key**: gestita nel backend come variabile d'ambiente,
  l'utente non vede nulla e non deve configurare niente
- **System prompt**: dinamico, costruito dal backend iniettando
  il contesto dell'utente (user_state, piano, log) ad ogni chiamata
- **Endpoint**: `POST /chat` con messaggio utente + history recente
- **Limiti di sicurezza**: l'LLM non può modificare user_state,
  piano o log direttamente. Può solo suggerire azioni che l'utente
  conferma e l'engine esegue

### 11.4 Cosa NON fa l'LLM

- Non genera piani (lo fa l'engine)
- Non calcola progressioni (lo fa progression_v1)
- Non modifica il macrociclo (lo fa il macrocycle generator)
- Non sceglie esercizi (lo fa il resolver)

L'LLM è l'interfaccia umana, non il cervello.

---

## 12. Decisioni tecniche (approvate)

| Decisione | Scelta | Motivazione |
|-----------|--------|-------------|
| **Persistenza** | JSON/JSONL | Semplice, funzionante, zero dipendenze. Migrazione DB se/quando serve multi-utente |
| **Frontend** | Next.js + React + Tailwind (PWA) | Mobile-first, Claude Code lo genera bene, PWA si installa su telefono, shadcn/ui + Recharts per UI/grafici |
| **Assessment** | Ogni 6 settimane | Mini-test integrati in sessioni normali, non invasivo |
| **Logging outdoor** | Integrato nella day view | Stessa interfaccia indoor/outdoor, outdoor aggiunge location+condizioni |
| **Feedback** | Granulare per esercizio | Piano vs realtà: l'utente registra gradi fatti, carichi usati, serie completate |
| **LLM Coach** | Claude Sonnet, key nel backend | Layer conversazionale sopra engine deterministico, utente non configura nulla |

---

## 13. Roadmap

### Fase 0: Dati + API (1-2 settimane) ✅
- [x] Caricare questo doc nel repo (`docs/DESIGN_GOAL_MACROCICLO_v1.1.md`)
- [x] Aggiornare CLAUDE.md con riferimento a questo doc
- [x] Ampliare catalogo esercizi (da 35 a ~102)
- [x] Ampliare catalogo sessioni (da 17 a ~28)
- [ ] API FastAPI: implementare tutti gli endpoint
- [ ] Aggiungere planning mode: `lead_focus`

### Fase 1: Macrociclo engine (2-3 settimane) ✅
- [x] Schema goal in user_state (`user_state.json` v1.5)
- [x] Assessment engine: `assessment_v1.py` — profilo 6 assi (0-100)
- [x] Macrociclo generator: `macrocycle_v1.py` — Hörst 4-3-2-1 con DUP
- [x] Planner v2: `planner_v2.py` — planner phase-aware
- [x] Deload: programmato + adattivo + pre-trip
- [x] Vocabulary update (§5.1-5.6)
- [x] Test per tutto il macrociclo engine (assessment, macrocycle, planner_v2)
- [ ] Adattività avanzata: readiness, overreach, plateau detection

### Fase 1.5: Fix post-E2E (completata) ✅
Test E2E manuale ha prodotto 14 finding (4 P0, 6 P1, 4 P2).
Risolti in due cluster di fix.
- [x] Cluster 1: resolver inline blocks, integration test sessioni
      reali, planner 2-pass con cycling e distribuzione uniforme,
      finger_maintenance_home, climbing-first ordering
- [x] Cluster 2: PE assessment con repeater test, replanner
      phase-aware (12 intent), validazione goal, floor minimo fasi,
      pre-trip deload reale, vocabulary sync
- [x] 155 test verdi (da 115)
- [x] 13/14 finding risolti (F14 outdoor → backlog)
- [x] docs/BACKLOG.md creato con 7+ item per fasi future

### Fase 1.75: Arricchimento sessioni (da fare)
Review letteratura (Hörst, Lattice, Eva López, Hooper's Beta) ha
evidenziato gap tra le sessioni attuali e i programmi reali.
- [ ] Sessioni serali da 5-7 blocchi (ora 2-3): warmup → finger
      → pulling → climbing on wall → core → antagonist/prehab
      → cooldown
- [ ] Template nuovi: pulling_strength, antagonist_prehab,
      limit_bouldering
- [ ] Arricchire sessioni esistenti: pulling in strength_long,
      core da opzionale a standard, antagonisti in ogni sessione
      serale
- [ ] Sessione core standalone per slot pranzo (B1)
- [ ] Sessione PE serale completa: 4x4/intervals + route volume
      + core + antagonist
- [ ] Verifica piano vs letteratura: confronto struttura macrociclo
      con Hörst 4-3-2-1, Lattice, Eva López
- [ ] Load score placeholder per sessione (low=20, medium=40,
      high=65, max=85) + weekly summary

### Fase 2: Tracking + extras (1-2 settimane)
- [ ] Schema outdoor session log
- [ ] Feedback granulare: piano vs realtà per ogni esercizio
- [ ] Logging climbing: gradi, stile, tentativi (indoor + outdoor)
- [ ] Trip planning: date trip → deload pre-trip automatico
- [ ] Catalogo citazioni motivazionali
- [ ] Report engine: settimanale + mensile (Python)

### Fase 3: UI (2-4 settimane)
- [ ] Setup Next.js + Tailwind + shadcn/ui + PWA
- [ ] Day view: "cosa fare oggi" + citazione + sessione risolta
- [ ] Feedback view: registra risultati per esercizio (gradi, carichi, RPE)
- [ ] Week view: piano settimanale, skip/move, outdoor
- [ ] Outdoor log view (integrato nella day view)
- [ ] Onboarding/Assessment wizard
- [ ] Report view: grafici progressi (Recharts)
- [ ] Guided session mode: timer per esercizi, rest timer automatico, beep/vibrazione
- [ ] Feedback automatico tempi (effettivo vs pianificato → closed loop)

#### Sessione guidata con timer (Guided Session Mode)

La UI deve supportare un'esperienza "sessione guidata" step-by-step:

1. L'utente apre la sessione risolta e la esegue passo-passo
2. Per ogni esercizio vede: nome, set/reps/tempo previsti, notes
3. Preme **Start** → parte timer (countdown per esercizi a tempo, cronometro per esercizi a reps)
4. Per esercizi a tempo (hang 7s, hollow hold 30s) → countdown con beep/vibrazione
5. Quando finisce il set → preme **Done** → parte automaticamente il **rest timer**
6. Il rest timer mostra il tempo di recupero effettivo vs pianificato:
   - Verde: dentro il range previsto
   - Giallo: 20%+ oltre il previsto
   - Rosso: 50%+ oltre il previsto
7. Quando il rest finisce → beep/vibrazione → propone set o esercizio successivo
8. Alla fine della sessione → schermata riepilogo con tempi reali vs pianificati

**Dati catturati automaticamente dal timer:**
- Tempo effettivo per set e per esercizio
- Rest effettivo vs rest previsto
- Durata totale sessione vs durata stimata
- Skip/modifiche (se l'utente salta un set o cambia esercizio)

**Note tecniche:**
- I dati per pilotare i timer sono già nei `prescription_defaults`: `rest_seconds`, `hold_seconds`, `duration_min`, `sets`, `reps`
- React: `useState` + `useEffect` con `setInterval`
- Web APIs: `Notification` + `Vibration` per alert, `Wake Lock API` per schermo acceso
- PWA: funziona anche offline (sessione risolta già nel client)

Questo feedback (tempo effettivo vs pianificato) alimenta il closed loop:
se un utente riposa sistematicamente più del previsto, potrebbe indicare
carico troppo alto o pattern da correggere.

### Fase 3.5: LLM Coach layer (1-2 settimane)
- [ ] Integrazione API Anthropic (Claude Sonnet) nel backend
- [ ] System prompt dinamico: inietta user_state + piano corrente + log recenti
- [ ] Endpoint `/chat`: conversazione con contesto completo dell'utente
- [ ] Casi d'uso:
  - Onboarding conversazionale (assessment guidato dal coach)
  - Coaching pre-sessione ("oggi mi sento stanco, che faccio?")
  - Analisi post-sessione ("come è andata?" → feedback strutturato)
  - Discussione climbing libera ("vado ad Arco, come mi preparo?")
  - Suggerimenti e citazioni motivazionali contestuali
- [ ] API key gestita nel backend (env var), utente non vede nulla
- [ ] Limiti: l'LLM suggerisce e conversa, NON modifica il piano
  direttamente. Ogni modifica passa dall'engine deterministico

### Fase 4: Evoluzione (ongoing)
- [ ] Più tipi di goal (boulder, all-round, outdoor_season)
- [ ] Report annuale
- [ ] P1 ranking nel resolver (recency, intensità, fatica)
- [ ] Periodizzazione multi-macrociclo (stagionale)
- [ ] Notifiche/reminder
