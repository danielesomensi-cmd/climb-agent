# Free Climbing Session + Tabata Timer — Design Document v2

> Autore: Daniele Somensi + claude.ai strategy session
> Data: 2026-03-19
> Status: DECISIONS CLOSED — ready for Claude Code briefs
> Briefs: A135 (Tabata), A136 (Free Session BE), A137 (Free Session FE), A138 (Integration)

---

## 1. Decisioni consolidate

| # | Domanda | Decisione |
|---|---------|-----------|
| 1 | Add-on data model | Opzione C: tutto in `free_sessions[]`, campo `context` (standalone/add_on/replacement) |
| 2 | Sostituzione vs coesistenza | 3 casi con dialog: (A) replace pianificata, (B) standalone su rest day, (C) add-on post sessione |
| 3 | Tab navigation | Due tab separati: **Tabata** + **Free Session** (bottom nav = Today, Week, Tabata, Free Session, Settings) |
| 4 | Template Pyramid | Fuori da v1 — troppo complesso |
| 5 | Grading | Fontainebleau per tutte le superfici, nessuna nota conversione |
| 6 | Boulder status | 3 stati: Flash / Sent / Attempted. Per lead: Onsight / Flash / Redpoint / Project |
| 7 | Tabata timer | Timer generico editabile (Seconds Pro style), nessun preset climbing |
| 8 | Persistenza | JSONB in `user_state.free_sessions[]` (stesso pattern outdoor_log) |
| 9 | Load score | Formula semplice v1: n° boulder × difficulty factor relativo al max |
| 10 | Weekly report | Riga semplice con stats chiave (n° climb, max grade, send rate, durata) |

---

## 2. FEATURE A: Tabata Timer

### 2.1 Concetto

Timer intervallato generico editabile, stile Seconds Pro. Tab dedicato nella bottom nav. Con le frasi motivazionali del voice pool già implementato (Alé duro!, Punani!, Vaffanculo!, Venga!, Let's go!, Send it!, You got this!, Crush!).

### 2.2 Parametri editabili

| Parametro | Default | Min | Max | UI |
|-----------|---------|-----|-----|----|
| Prepare | 10s | 0 | 60 | +/- buttons |
| Work | 40s | 5 | 300 | +/- buttons |
| Rest | 10s | 0 | 120 | +/- buttons |
| Cycles | 8 | 1 | 50 | +/- buttons |
| Sets | 1 | 1 | 10 | +/- buttons |
| Rest between sets | 60s | 0 | 300 | +/- buttons |
| Cool down | 0s | 0 | 120 | +/- buttons |

### 2.3 Computed display

- **Total time**: calcolato in tempo reale (come Seconds Pro: "13:19")
- **Total intervals**: calcolato (es. "32 intervals")
- Formula: `total = prepare + (work + rest) × cycles × sets + rest_between_sets × (sets - 1) + cool_down`

### 2.4 Timer running UI

```
┌─────────────────────────────────────┐
│           TABATA TIMER              │
│                                     │
│           ┌─────────┐               │
│           │  WORK   │               │
│           │  0:37   │               │
│           └─────────┘               │
│                                     │
│     Cycle 3/8  ·  Set 1/1          │
│                                     │
│     Total elapsed: 2:15             │
│     Remaining: 11:04                │
│                                     │
│  [⏸ PAUSE]     [⏹ STOP]           │
└─────────────────────────────────────┘
```

### 2.5 Behavior

- **Phases cycle**: Prepare → (Work → Rest) × Cycles → Rest between sets → repeat Sets → Cool down
- **Colors**: Work = active color (teal/green), Rest = muted color, Prepare/Cool down = neutral
- **Voice**: same pool as exercise timer, ~30% random phrase on Work start, "Go" for 70%
- **Sound**: beep on phase transition (work→rest, rest→work)
- **Tap**: tap anywhere = pause/resume (same pattern as exercise timer)
- **Expand**: reuse existing timer expand button/mode (A123)
- **Background**: must survive iOS Safari PWA suspension (wall-clock based)
- **Completion**: voice "Done!" or random phrase, show summary (total time, cycles completed)

### 2.6 UI Layout (setup screen)

Same visual pattern as the Seconds Pro screenshots — vertical list of parameters with +/- buttons, icons on the left, total time + intervals displayed at the top.

---

## 3. FEATURE B: Free Climbing Session

### 3.1 Surfaces supported

| Surface | Equipment | Grading | Notes |
|---------|-----------|---------|-------|
| Gym Boulder | `gym_boulder` | Fontainebleau | Gym problems |
| Board — Kilter | `board_kilter` | Fontainebleau | |
| Board — Moon | `board_moonboard` | Fontainebleau | |
| Board — Other | `board_other` | Fontainebleau | Tension, Grasshopper, custom |
| Lead | `gym_routes` | Fontainebleau | Routes with style tracking |

Outdoor: out of scope v1 (→ Outdoor Redesign).

### 3.2 Two modes

**Template mode ("Dimmi cosa fare")**: user selects a preset → system suggests grade target, rest times, n° climbs, and phase-aware tips.

**Free mode ("Faccio da solo")**: no structure. Phase tip shown, manual rest timer, open logger.

### 3.3 Template presets (v1)

#### Boulder presets (gym + board)

| Preset ID | Name | Purpose | Grade offset | Rest | Target climbs | Duration |
|-----------|------|---------|-------------|------|---------------|----------|
| `free_volume` | Volume | High volume, moderate grade | -2/-3 | 2-3 min | 15-25 | 60-90 min |
| `free_projecting` | Projecting | Few climbs, limit grade | 0/+1 | 5-8 min | 5-10 | 60-90 min |
| `free_endurance` | Endurance | Circuits, easy boulders in series | -3/-4 | 1-2 min | 20-30 | 45-75 min |
| `free_technique` | Technique | Technical drills on easy problems | -3/-4 | 2-3 min | 15-20 | 45-60 min |

#### Lead presets

| Preset ID | Name | Purpose | Grade offset | Rest | Target routes | Duration |
|-----------|------|---------|-------------|------|---------------|----------|
| `free_lead_volume` | Volume | Many routes, moderate | -2 from lead_max_rp | 5-8 min | 6-10 | 60-90 min |
| `free_lead_projecting` | Projecting | Project 1-2 limit routes | 0/+1 from lead_max_rp | 10-15 min | 2-4 | 60-90 min |
| `free_lead_endurance` | Endurance | Long easy routes, less rest | -3 from lead_max_os | 3-5 min | 8-12 | 60-90 min |

### 3.4 Phase compatibility matrix

| Preset | Base | S&P | PE | Performance | Deload |
|--------|------|-----|-----|-------------|--------|
| Volume | ✅ | ⚠️ | ✅ | ⚠️ | ❌ |
| Projecting | ⚠️ | ✅ | ⚠️ | ✅ | ❌ |
| Endurance | ✅ | ⚠️ | ✅ | ⚠️ | ✅ |
| Technique | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3.5 Phase tips

#### Template mode tips

| Phase | Volume | Projecting | Endurance | Technique |
|-------|--------|------------|-----------|-----------|
| Base | "Ottima scelta! Gradi moderati, rest ≥2min. Focus qualità di movimento." | "In Base è meglio il volume. Se vuoi provare, max 3-4 tentativi al limite." | "Perfetto per la Base. Mantieni la pompa bassa." | "Ideale. Ogni boulder è un'occasione per migliorare i piedi." |
| S&P | "OK, ma non esagerare col volume — le dita servono per i max hang." | "Fase ideale! Riposa a lungo (5-8min), qualità massima." | "Meglio dopo S&P work, non prima. Tieni leggero." | "Sempre utile, ma non stancarti prima del lavoro di forza." |
| PE | "Buona scelta, complementare al PE. Gradi moderati, ritmo costante." | "OK se hai recuperato dal PE work. Altrimenti volume." | "Perfetto, è il tuo pane in questa fase." | "OK come riscaldamento o cooldown." |
| Perf | "Riduci volume del 30%. Il corpo si sta affilando." | "Sì! Ma solo 100% fresco. Pochi tentativi, massima qualità." | "Leggero. Non stancare i sistemi prima della performance." | "Perfetto come prep mentale." |
| Deload | "Max 10-12 boulder, gradi bassi. Muoviti con piacere, zero sforzo." | "No projecting in deload. Volume leggero o technique." | "Leggero OK. Se senti pump, fermati." | "Ideale per il deload. Divertiti." |

#### Free mode tips (one per phase)

| Phase | Tip |
|-------|-----|
| Base | "Fase Base: scala tanto, scala facile. Gradi a -2/-3 dal max. Riposa ≥2min. Se ti pompi, stai andando troppo forte." |
| S&P | "Fase Strength & Power: prova il tuo limite, ma riposa a lungo (5-8 min) e non insistere oltre 3-4 tentativi per boulder." |
| PE | "Fase Power Endurance: volume con ritmo. Boulder moderati, rest corto (1-2 min), cerca il pump controllato." |
| Perf | "Fase Performance: scala come ti senti. Il corpo è pronto. Ascoltalo." |
| Deload | "Deload: scala per piacere. Gradi facili, zero sforzo, goditi il movimento." |

### 3.6 UI Flow

#### Entry points (2)

1. **Tab "Free Session"** nella bottom nav → seleziona superficie → flow
2. **Quick-add in Today/Week view** → "Free Climbing Session" → stesso flow

#### Flow steps

```
Step 1: SURFACE
  Seleziona: Gym Boulder / Kilter / Moon / Other Board / Lead
  (mostra solo equipment dell'utente)

Step 2: GYM (skip se 1 sola palestra compatibile)
  Seleziona palestra

Step 3: MODE
  ┌──────────────────────┐  ┌──────────────────────┐
  │  📋 TEMPLATE          │  │  🧗 FREE              │
  │  "Dammi una struttura"│  │  "Faccio da solo"    │
  └──────────────────────┘  └──────────────────────┘

Step 3b: TEMPLATE SELECTION (solo se Template mode)
  Card selezionabili: Volume / Projecting / Endurance / Technique
  Ogni card: nome, icona, 1 riga desc, badge fase (✅/⚠️/❌), grade target preview

Step 4: ACTIVE SESSION
  (ClimbLogger — vedi §3.7)

Step 5: SUMMARY
  (vedi §3.8)
```

#### Context-aware dialog (quando c'è sessione pianificata)

Se l'utente avvia Free Session da un giorno con sessione pianificata NON completata:
- Dialog: "Hai [Boulder Strength Gym] pianificata oggi. Vuoi:"
  - "Sostituirla" → pianificata diventa skipped, context = "replacement"
  - "Aggiungerla in più" → coesistono, context = "standalone"

Se la sessione pianificata è GIÀ completata:
- Nessun dialog, context = "add_on" automaticamente

Se giorno rest / nessuna sessione:
- Nessun dialog, context = "standalone"

### 3.7 ClimbLogger component

#### Boulder mode (template)

```
┌─────────────────────────────────────┐
│  Volume · Kilter · BKL              │
│  Target: ~6b  ·  Rest: 3 min       │
│                                     │
│  ┌─ TIP ──────────────────────────┐ │
│  │ Base phase: keep it moderate,   │ │
│  │ focus on movement quality.      │ │
│  └─────────────────────────────────┘ │
│                                     │
│  [grade picker: 6b]                 │
│  ( ) Flash  ( ) Sent  ( ) Attempted │
│  [attempts: __ ] (if Sent/Attempted)│
│  [notes: _________ ] (optional)     │
│  [LOG BOULDER]                      │
│                                     │
│  ── logged ──                       │
│  #1: 6a+ ⚡ flash                   │
│  #2: 6b  ✅ sent (2 att)            │
│  #3: 6b+ ❌ attempted (3 att)       │
│                                     │
│  ┌── REST TIMER: 2:47 ───────────┐ │
│  │  [Skip]  [+1 min]              │ │
│  └─────────────────────────────────┘ │
│                                     │
│  Boulders: 3/20  ·  Elapsed: 22min │
│  [FINISH SESSION]                   │
└─────────────────────────────────────┘
```

**Template mode behavior:**
- Rest timer auto-starts after LOG BOULDER
- Grade picker defaults to template target grade
- Counter shows progress vs target (3/20)
- Voice on rest timer end (~30% random phrase)

#### Boulder mode (free)

Same ClimbLogger but:
- No target grade (picker starts from last logged grade or empty)
- No counter target (just total: "Boulders: 3")
- Rest timer is manual (button "Start rest timer", not automatic)
- Tip is generic phase tip

#### Lead mode

Additional fields per climb:
- **Style**: Onsight / Flash / Redpoint / Project (button group)
- **Topped**: Yes / No (toggle)
- **Attempts**: number (if Project)

```
  [grade picker: 6b+]
  Style: [OS] [FL] [RP] [PROJ]
  ( ) Topped  ( ) Fell
  [attempts: __ ] (if Project)
  [notes: _________ ]
  [LOG ROUTE]
```

### 3.8 Session Summary

```
┌─────────────────────────────────────┐
│  Session Complete! 🧗               │
│                                     │
│  Kilter · BKL · Volume              │
│  Duration: 1h 12min                 │
│                                     │
│  Boulders: 18                       │
│  Flashed: 8  Sent: 8  Attempted: 2 │
│  Max grade sent: 6c                 │
│  Send rate: 89%                     │
│                                     │
│  Grade distribution:                │
│    6a  ████ 4                       │
│    6a+ ██████ 6                     │
│    6b  ████ 4                       │
│    6b+ ██ 2                         │
│    6c  █ 1                          │
│    6c+ █ 1 (attempted)              │
│                                     │
│  How did it feel?                   │
│  [😴 Easy] [👍 Good] [💪 Hard]     │
│                                     │
│  Notes: _________________________   │
│                                     │
│  [SAVE]                             │
└─────────────────────────────────────┘
```

### 3.9 Data model

#### Free session record (in user_state.free_sessions[])

```json
{
  "id": "free_20260319_1",
  "date": "2026-03-19",
  "context": "add_on",
  "session_mode": "template",
  "preset_id": "free_volume",
  "surface": "board_kilter",
  "gym_name": "BKL",
  "phase_at_time": "base",
  "started_at": "2026-03-19T18:30:00Z",
  "finished_at": "2026-03-19T19:42:00Z",
  "duration_minutes": 72,
  "climbs": [
    {
      "index": 1,
      "grade": "6a+",
      "status": "flash",
      "attempts": 1,
      "style": null,
      "topped": null,
      "notes": null,
      "logged_at": "2026-03-19T18:35:00Z"
    },
    {
      "index": 2,
      "grade": "6b",
      "status": "sent",
      "attempts": 2,
      "style": null,
      "topped": null,
      "notes": null,
      "logged_at": "2026-03-19T18:42:00Z"
    },
    {
      "index": 3,
      "grade": "6c+",
      "status": "attempted",
      "attempts": 3,
      "style": null,
      "topped": null,
      "notes": "Couldn't stick the dyno",
      "logged_at": "2026-03-19T19:05:00Z"
    }
  ],
  "summary": {
    "total_climbs": 18,
    "flashed": 8,
    "sent": 8,
    "attempted": 2,
    "max_grade_sent": "6c",
    "max_grade_attempted": "6c+",
    "send_rate": 0.89
  },
  "overall_feel": "good",
  "notes": "First volume session on Kilter, felt strong",
  "load_score": 42.5
}
```

Lead climbs additionally have:
```json
{
  "style": "onsight",
  "topped": true
}
```

#### Load calculation (v1 — simple)

```
For each climb:
  grade_value = font_to_numeric(grade)  // 6a=1, 6a+=2, 6b=3, ...
  user_max_value = font_to_numeric(user_boulder_max_rp)
  relative_difficulty = grade_value / user_max_value  // 0.0 to 1.2+

  climb_load = relative_difficulty × status_weight
    status_weight: flash = 0.8, sent = 1.0, attempted = 0.6
    × attempt_modifier: 1 att = 1.0, 2 att = 1.1, 3+ att = 1.3

total_load = Σ(climb_load)
```

This feeds into weekly load total alongside engine sessions.

### 3.10 Relation with existing features

- **NOT an other_activity**: free_climbing is its own session type with rich data
- **other_activity** remains for non-climbing (yoga, running, etc.)
- **Does NOT update** working_loads or baselines (not a test)
- **Counts as** "day done" for adherence
- **Load ripple**: load_score enters weekly total, planner considers it next day
- **Weekly report**: single line — "Free climbing · Kilter · 18 boulders · max 6c · 89% send · 72 min"

### 3.11 Vocabulary updates needed

New enum values:
```
session_type += "free_climbing"
session_mode: "template" | "free"
context: "standalone" | "add_on" | "replacement"
climb_status: "flash" | "sent" | "attempted"
climb_style: "onsight" | "flash" | "redpoint" | "project"  (lead only)
```

New preset IDs:
```
free_volume, free_projecting, free_endurance, free_technique
free_lead_volume, free_lead_projecting, free_lead_endurance
```

---

## 4. Out of scope v1

- Outdoor climbing (→ Outdoor Redesign)
- Pyramid template (→ v2)
- Board-specific grades (Kilter/Moon native grades)
- LLM-generated tips (→ Phase 3.5)
- Historical stats/progression for free sessions
- Import from Kilter/Moon apps
- Social Session / games with friends
- Climbing preset for Tabata timer (just generic timer v1)
