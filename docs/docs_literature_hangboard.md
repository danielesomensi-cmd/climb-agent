# climb-agent — Literature Sources: Hangboard Exercises

**File:** `docs/docs_literature_hangboard.md`
**Scope:** Esercizi hangboard — fonti per validare e compilare tutti i campi
**Ultimo aggiornamento:** 2026-02-20 (sessione 2 — aggiornamento con correzioni da fonti primarie)
**Stato:** Seconda ricerca completata — correzioni importanti su density hangs e min_edge_hang

---

## Come leggere questo file

Per ogni esercizio:
- Ogni riga fonte è una riga della tabella (più fonti per lo stesso esercizio = più righe)
- I campi validati sono evidenziati con ✅, quelli incerti con ⚠️, quelli mancanti con ❌
- `video_url` = link diretto YouTube/Vimeo se trovato, `null` altrimenti

Legenda colonne tabella:
| sets | reps | work_s | rest_rep_s | rest_set_s | intensity_level | edge_mm | grip | description/cues |

---

## Avvertenza sui valori "range"

Dove la letteratura fornisce un range (es. 3–5 serie), il campo JSON usa il valore **basso** del range come default. Il range completo è documentato qui per contesto.

---

## ⚠️ Correzioni da applicare ai JSON (sessione 2)

Queste correzioni sono emerse dalla lettura diretta della fonte primaria (trainingforclimbing.com, Hörst 2022 article), da confrontare con i JSON correnti prima di applicare.

| # | Esercizio | Campo | Valore attuale JSON | Valore corretto | Fonte | Confidenza |
|---|-----------|-------|---------------------|-----------------|-------|------------|
| 1 | `min_edge_hang` | `work_seconds` | 7s | **12s** | Hörst T4C 2022: "hang exactly 12s, choose edge barely holdable for 15s" | ⭐⭐⭐ Alta |
| 2 | `max_hang_5s` | `sets` | 6 | **5** (max) | Hörst T4C: "2–5 sets", López: "3–5 sets" — 6 sopra range | ⭐⭐ Media |
| 3 | `density_hangs` | struttura | 10s/10s × 6 reps | **30–40s to near-failure × 2–3 reps, 3–5 min rest** | Nelson C4HP diretto | ⭐⭐⭐ Alta |
| 4 | `density_hang_10_10` | nota | — | Questo esercizio è una **semplificazione** non canonica del Nelson. Potrebbe valere la pena rinominarlo. | Nelson C4HP diretto | ⭐⭐ Media |
| 5 | `horst_7_53` | `sets` | 4 | **massimo 5** (4 è ok come default) | Hörst T4C: "do not exceed 5 sets" | ✅ Già corretto |
| 6 | `max_hang_7s` | `sets` | 6 | **5** (max) | Hörst T4C: "2–5 sets", López: "3–5 sets" — 6 sopra range (stessa correzione di max_hang_5s) | ⭐⭐ Media |

---

---

## 1. max_hang_5s

**Protocollo:** 5 secondi max — Hörst / López MaxHangs MAW (variante corta)

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip | Note |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|------|
| 1 | Hörst, Training For Climbing (trainingforclimbing.com) | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 2–5 | — | 10s (target: fall at 13s) | — | 180s | 80–95% MVC | 20mm | half_crimp | ✅ Hörst usa 10s come "standard" ma 5s è variante per MVC più alto; edge 20mm confermato |
| 2 | Lattice Training (climbing.com) | 2022 | https://www.climbing.com/skills/lattice-hangboarding-part-2/ | — | — | — | — | — | 80–95% | 20mm | half_crimp | ✅ "Max hangs classically prescribed in the 80-95% range" su 20mm edge |
| 3 | López-Rivera, Sportphysio (ResearchGate) | 2021 | https://www.researchgate.net/publication/362068736 | — | — | 5s | — | 180–240s | ~90–100% MVC | 14–20mm | half_crimp | ✅ Ricerca scientifica; MaxHangs MAW = massima intensità su 18mm edge |

**Validazione campi JSON:**
- `sets: 6` ⚠️ (Hörst dice 2–5, il nostro 6 è sopra — **considerare ridurre a 5**)
- `work_seconds: 5` ✅
- `rest_between_sets_seconds: 180` ✅
- `intensity_level: "max"` ✅
- `edge_mm: 20` ✅
- `grip: "half_crimp"` ✅

**video_url:** `null` — `[da verificare: Cameron Hörst T4C channel]`

**Description (da scrivere):**
> Isometric max hang on a 20mm edge at 90–100% effort for 5 seconds. Develops maximum neural recruitment and peak finger force (MaxHangs MAW protocol, López/Hörst).

**Cues (da scrivere):**
- Lock scapulae down and back before hanging
- Half crimp: DIP joint straight, PIP bent ~90°
- Drive elbows slightly forward to engage lats
- Breathe out on engagement, do not hold breath
- Add weight until barely able to complete the hang

---

## 2. max_hang_7s

**Protocollo:** 7 secondi max — Hörst "7-53" single hang unit / López MaxHangs MED

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Hörst, T4C (trainingforclimbing.com) | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 2–5 | — | 10s ("fall at 13s") | — | 180s | 80–95% | 20mm | half_crimp |
| 2 | Cameron Hörst video (trainingforclimbing.com) | 2020 | https://trainingforclimbing.com/video-advanced-hangboard-training-protocol/ | 3–5 | — | 7s | 53s | 180–300s | 90–95% | 20mm | half_crimp |
| 3 | strengthclimbing.com analisi 7-53 | 2020 | https://strengthclimbing.com/eric-horst-7-53-hangboard-routine/ | 3–5 | — | 7s | 53s | 180s | 90–95% | 20mm | half_crimp |

**Validazione campi JSON:**
- `sets: 5` ⚠️ (range 3–5, 5 è il massimo consigliato — **JSON attuale ha 6, da ridurre a 5**)
- `work_seconds: 7` ✅
- `rest_between_sets_seconds: 180` ✅
- `edge_mm: 20` ✅
- `grip: "half_crimp"` ✅

**video_url:** `null` — `[da cercare: video Cameron Hörst T4C YouTube channel]`

**Description (da scrivere):**
> 7-second max hang at near-maximal intensity. Targets alactic energy system without inducing pump. Foundation of Hörst's strength protocol.

**Cues:**
- Choose load: can barely complete 10s hang (90–95% MVC)
- No pump should be felt during or after the session
- Shoulders packed throughout — no passive hanging
- Progress: add 2kg every session when hang feels manageable
- Last set should be a struggle; if not, increase load

---

## 3. max_hang_10s_lev1

**Protocollo:** 10 secondi — López MaxHangs standard / Hörst "Maximum Weight 10-second"

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Hörst, T4C (fonte primaria) | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 2–5 | — | 10s | — | 180s (5 min inter-set) | 80–90% | 14–20mm | half_crimp |
| 2 | López-Rivera, Sportphysio | 2021 | https://www.researchgate.net/publication/362068736 | 3–5 | — | 10s | — | 180–240s | 85–90% | 14–20mm | half_crimp |
| 3 | UKC discussion (Eva López protocol) | vari | https://www.ukclimbing.com/forums/walls+training/eva_lopez_training_plan-541174 | 3–5 | — | 10s | — | 180–240s | ~90% | 14–20mm | half_crimp |

**Prescrizione Hörst (fonte diretta, 2022):**
> "Do a 10-second hang using a feature that you can barely hold for 13 seconds with maximum effort. Adjust weight as needed. Rest exactly 3 minutes. Do four more hangs. After the first set of five hangs, rest at least 5 minutes before second set."

**Validazione:**
- `sets: 5` ✅ (5 hang per set, fino a 2 set)
- `work_seconds: 10` ✅
- `rest_between_sets_seconds: 180` ✅ (ma inter-set rest = 5 min, valore 180 è intra-set rest tra hang)
- `intensity_level: "high"` ✅ (85–90%, non max)
- `edge_mm: 20` ✅ (Hörst consiglia 14–20mm per questa variante)

**⚠️ Nota struttura:** Hörst chiarisce che per questo protocollo il "rest" di 3 min è tra ogni singolo hang all'interno di un set, non tra set. Il rest inter-set è 5 min. Da verificare come è modellato nel JSON.

**video_url:** `null`

---

## 4. max_hang_ladder (Max Hang Pyramid)

**Protocollo:** Hörst / Bechtel 3-6-9 Ladder — 3 intensità crescenti

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | strengthclimbing.com (riferimento Bechtel) | 2020 | https://strengthclimbing.com/eva-lopez-maxhangs/ | 3 | — | 10s | — | 180s | 75–95% (ascending) | 20mm | half_crimp |
| 2 | Hörst, T4C podcast #10 | 2017 | https://trainingforclimbing.com/podcast-10-maximum-strength-fingerboard-training/ | 3 | — | 10s | — | 180s | scalato 3 step | 20mm | half_crimp |

**Validazione:**
- `sets: 3` ✅ (una "scala" = 3 hangs a intensità crescente)
- `work_seconds: 10` ✅
- `rest_between_sets_seconds: 180` ✅

**video_url:** `null`

---

## 5. horst_7_53

**Protocollo:** Hörst "7-53" — protocollo signature Eric/Cameron Hörst

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Hörst, T4C — fonte primaria 2022 | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | max 5 | 3 | 7s | 53s | 180–300s | 90–95% | 14–20mm | half_crimp |
| 2 | Cameron Hörst video (T4C) | 2020 | https://trainingforclimbing.com/video-advanced-hangboard-training-protocol/ | 3–5 | 3 | 7s | 53s | 180–300s | 90–95% | 20mm | half_crimp |
| 3 | strengthclimbing.com analisi | 2020 | https://strengthclimbing.com/eric-horst-7-53-hangboard-routine/ | 3–5 | 3 | 7s | 53s | 180s | 90–95% | 20mm | half_crimp |

**Prescrizione Hörst (fonte diretta, 2022):**
> "Do a 7-second hang using a feature that you can barely hold for 10 seconds. Rest for exactly 53 seconds. Do two more hangs. Each hang-rest couplet takes exactly 1 minute. After the first set of three hangs, rest 3 to 5 minutes before doing a second set. Limit yourself to a maximum of five sets."

**Validazione campi JSON:**
- `sets: 4` ✅ (range 3–5, max 5 — 4 come default è ok)
- `reps: 3 hangs per set` — struttura: 3 hangs × (7s + 53s) = 3 min per set
- `work_seconds: 7` ✅
- `rest_between_reps_seconds: 53` ✅ (caratteristica fondamentale: resintesi PCr)
- `rest_between_sets_seconds: 180` ✅ (range 3–5 min)
- `intensity_level: "high"` ✅
- `edge_mm: 14–20mm` ✅ — Hörst ora specifica anche pockets 2 dita e monos per avanzati
- **Frequenza: 2× settimana max** ✅

**Note importanti (confermate 2022):**
- 53 secondi non è arbitrario: phase 1 resintesi PCr dura ~50s (conferma dalla fisiologia muscolare)
- Iniziare con half_crimp e open_crimp — un set per ciascuno
- Avanzati: aggiungere set per 2-finger pockets e pinch

**video_url:** `null` — `[da cercare: Cameron Hörst T4C channel YouTube]`

---

## 6. repeater_hang_7_3

**Protocollo:** 7/3 Repeaters — Anderson Brothers / Hörst

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Hörst, T4C — fonte primaria 2022 | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 1–3 | 6 | 7s | 3s | 180s | 60–80% MVC con peso | vari | half_crimp |
| 2 | strengthclimbing.com | 2020 | https://strengthclimbing.com/hangboard-repeaters/ | 1–3 | 6 | 7s | 3s | 120–180s | 60–80% | 20mm | half_crimp |
| 3 | TrainingBeta, Lattice T. | 2018 | https://www.trainingbeta.com/comparing-hangboard-protocols/ | vari | 6 | 7s | 3s | 180s | 60–80% | vari | half_crimp |
| 4 | Cameron Hörst (T4C video) | 2019 | https://trainingforclimbing.com/hangboard-finger-training-repeaters/ | 1–3 | 6 | 7s | 3s | 120–180s | 60–80% | 20mm | half_crimp |

**Prescrizione Hörst (fonte diretta, 2022):**
> "Each set is comprised of 6 hang-rest intervals consisting of a 7-second hang and 3-second rest. Therefore, each 6-hang set will take about 1 minute. Add weight as needed. Rest three minutes between sets."

**Note Hörst importanti (2022):**
- Selezionare 3–7 grip type diversi per sessione
- Da 1 set (entry-level) a 3 set (avanzato) per ogni grip position
- Questo protocollo è "bridge between max strength and endurance training"
- Peso aggiunto: molto meno che nei protocolli max strength

**Validazione campi JSON:**
- `sets: 3` ✅
- `reps: 6` ✅ (6 hangs × 7s = ~1 min TUT per set)
- `work_seconds: 7` ✅
- `rest_between_reps_seconds: 3` ✅
- `rest_between_sets_seconds: 180` ✅
- `intensity_level: "medium"` ✅ (60–80% MVC)

**video_url:** `null` — `[Cameron Hörst 7/3 Repeater — T4C YouTube channel, da trovare ID]`

**Description:** Intermittent dead hangs: 7s on / 3s off repeated 6 times per set. Trains strength endurance by stressing both alactic and glycolytic energy systems.

**Cues:**
- Load: 60–80% MVC (get pumped but complete all reps)
- Shoulders active throughout — never passively hanging
- Use pulley/band to reduce bodyweight if needed
- Breathe continuously; exhale during hang
- If failing before rep 6, reduce load; if not pumped, increase

---

## 7. repeater_15_15

**Protocollo:** 15/15 Repeaters — López / Hörst endurance variant

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | López-Rivera, Sportphysio | 2021 | https://www.researchgate.net/publication/362068736 | 3–8 | 4–5 | 10–15s | 15s | 60–120s | 60–80% MVC | 10–20mm | half_crimp |
| 2 | strengthclimbing.com (IntHangs analysis) | 2019 | https://strengthclimbing.com/eva-lopez-inthangs/ | 3–8 | 4–5 | 7–15s | 5–15s | 60–120s | 60–80% | variabile | half_crimp |

**Validazione:**
- `sets: 4` ✅ (range 3–8)
- `reps: 6` ⚠️ — López dice 4–5; nostro 6 è leggermente alto, accettabile
- `work_seconds: 15` ✅
- `rest_between_reps_seconds: 15` ✅
- `rest_between_sets_seconds: 120` ✅
- `intensity_level: "medium"` ✅ (40–60% MVC per questa variante)

**video_url:** `null`

---

## 8. density_hang_10_10

**Protocollo:** Density Hangs variante "10/10" — semplificazione del protocollo Nelson

> ⚠️ **NOTA CORREZIONE IMPORTANTE (sessione 2):**
> Questa è una semplificazione del protocollo originale di Tyler Nelson. Il protocollo canonico Nelson C4HP prevede hang di **30–40 secondi a near-failure** (~75% MVC, RPE 9–9.5), non 10s/10s. Il "10/10" esiste come variante ma non è la prescrizione standard. Vedere esercizio `density_hangs` per il protocollo completo.

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | strengthclimbing.com (Tyler Nelson reference) | 2021 | https://strengthclimbing.com/dr-tyler-nelsons-density-hangs-finger-training-for-rock-climbing/ | 2–3 per grip | 2–3 | 10s | 10s | 180–300s | ~75% MVC | 20mm | open_hand |
| 2 | TrainingBeta (comparison) | 2018 | https://www.trainingbeta.com/comparing-hangboard-protocols/ | 3–5 | 6 | 10s | 5–10s | 180s | 50–70% | 20mm | half_crimp |

**Validazione:**
- `sets: 3` ✅
- `reps: 6` ⚠️ — Nelson dice 2–3 reps per grip, fino a failure; 6 è troppo per il protocollo canonico
- `work_seconds: 10` ⚠️ — Nelson usa 30–40s; 10s è variante semplificata
- `rest_between_sets_seconds: 180` ✅

**video_url:** `null`

---

## 9. density_hangs (protocollo canonico Nelson)

**Protocollo:** Density Hangs — Tyler Nelson C4HP / Camp4 Human Performance

> ✅ **Questo è il protocollo CANONICO originale** di Tyler Nelson, a differenza del `density_hang_10_10`.

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------| 
| 1 | strengthclimbing.com — analisi dettagliata | 2021 | https://strengthclimbing.com/dr-tyler-nelsons-density-hangs-finger-training-for-rock-climbing/ | 2–3 per grip | 2–3 (near failure) | 30–40s | — | 180–300s (3–5 min) | ~75% MVC |
| 2 | TrainingBeta — Nelson intervista TBP 133 | 2021 | https://www.trainingbeta.com/media/tyler-simple-fingers/ | vari | 3 | 30–45s | — | — | bodyweight ~75% |
| 3 | PitchSix (pratico) | 2020 | https://pitchsix.com/blogs/academy/do-density-hangs-for-better-tendon-health | 3–4 grip × 3 reps | 3 | 30s | — | 90–120s | RPE 9–9.5 |

**Prescrizione Nelson (fonti dirette 2021):**
> Da TBP 133 (Nelson in persona): "I do open hand density hangs on the Beastmaker — that usually lasts 30–45 seconds. I'll do three of those with two arms."
>
> Da strengthclimbing.com (analisi Nelson): "Perform 2–3 reps until you fail. If you can do more than 3 reps, increase duration of last rep until you fail. For each hold position, perform 2–3 sets. That amounts to 4–9 sets per training session. According to Dr. Nelson, doing 8 sets is often the ideal training volume."

**Note Nelson importanti:**
- Target: ~75% MVC (non bodyweight per tutti — forti usano assistenza, più forti bodyweight, fortissimi 1-arm)
- Grip preferita Nelson: open hand (non half crimp!)
- Carico ideale: se riesci più di 3 reps senza failure, aumenta il carico
- 8 set totali considerato volume ottimale per sessione (Nelson)
- Possibile fare hanging su fingerboard o "no-hang" (pushing up on edge a terra)

**Validazione campi JSON (da rivedere):**
- `work_seconds: 30` ✅ (basso del range 30–45s)
- `rest_between_sets_seconds: 180` ✅ (min; ideale 3–5 min)
- `intensity_level: "medium"` ⚠️ — Nelson dice ~75% MVC = high-medium, RPE 9–9.5 su quella durata

**video_url:** `null` — `[da cercare: C4HP Tyler Nelson YouTube density hangs]`

---

## 10. long_duration_hang (Long Duration Hang — Tendon Health)

**Protocollo:** Lattice Training — long duration hangs per salute tendini / condizionamento

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Lattice Training (climbing.com Part 2) | 2022 | https://www.climbing.com/skills/lattice-hangboarding-part-2/ | 4–8 | — | 30–60s | — | 60–120s | RPE 5–7 | 20mm | half_crimp |

**Note Lattice importanti:**
- "Reps typically 30–60 seconds, repeated for 4–8 sets"
- "Recommend 2-arm position with pulley assist for most"
- "Shorter 15–30s for new grip positions conditioning"
- Lattice ha cambiato posizione su questo metodo: "spent a couple years collecting data — no longer strongly advocate to-failure long hangs"

**Validazione:**
- `sets: 5` ✅ (range 4–8)
- `work_seconds: 30` ⚠️ — nel JSON è impostato a 30s, Lattice dice 30–60s, ok come valore basso
- `rest_between_sets_seconds: 90` ✅

**video_url:** `null` — `[Lattice YouTube — da cercare Tom Randall hangboard tutorial]`

---

## 11. min_edge_hang (Minimum Edge Hang)

**Protocollo:** López MaxHangs MED — minimum edge depth, no added weight

> ⚠️ **CORREZIONE IMPORTANTE (sessione 2):** Il valore `work_seconds` attuale nel JSON è **7s** ma tutte le fonti primarie indicano **12s**. Vedere dettaglio sotto.

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------|------|
| 1 | Hörst, T4C — fonte primaria 2022 | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 1–2 | 5 per set | **12s** | — | 180s (3 min intra-set); 300s (5 min inter-set) | ~90–95% | variabile MED | half_crimp |
| 2 | strengthclimbing.com (MaxHangs MED) | 2023 | https://strengthclimbing.com/eva-lopez-maxhangs/ | 3–4 | — | 10s | — | 180–240s | ~90% MVC | variabile (MED) | half_crimp |
| 3 | López-Rivera, Sportphysio | 2021 | https://www.researchgate.net/publication/362068736 | 3–5 | — | 10s | — | 180–240s | 85–95% | 10–18mm | half_crimp |

**Prescrizione Hörst (fonte diretta, 2022):**
> "Do a 12-second hang using a feature that you can barely hold for 15 seconds with maximum effort. Rest for exactly 3 minutes. Do four more hangs. After doing the first set of five hangs, rest for 5 minutes before doing a second set of five hangs."

**Nota:** MED = la profondità minima di bordo su cui riesci a mantenere un hang controllato a 90% sforzo senza peso aggiunto. Progredisce riducendo il bordo settimana dopo settimana.

**Validazione — CORREZIONE:**
- `work_seconds: 7` ❌ → da aggiornare a **12s** (Hörst fonte primaria, 2022)
  - López dice 10s, Hörst dice 12s. Divergenza minore. Raccomandazione: **12s** (fonte più recente e diretta)
- `sets: 5` ✅ (fino a 2 set × 5 hang — totale 10 hang)
- `rest_between_sets_seconds: 180` ✅ (ma intra-hang rest = 3 min, inter-set = 5 min — stessa struttura del 10s protocol)
- `edge_mm: 20` ⚠️ — il valore dipende dall'atleta (MED = bordo minimo individuale), 20mm è solo un punto di partenza
- `intensity_level: "max"` ✅ (RPE 9–9.5)

**video_url:** `null`

---

## 12. dead_hang_easy

**Protocollo:** Dead hang bodyweight, bassa intensità — riscaldamento / condizionamento tendinoso

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------| 
| 1 | Lattice Training (Part 1) | 2022 | https://www.climbing.com/skills/tom-randalls-guide-to-better-hangboarding-part-1/ | 3–5 | — | 10–15s | — | 60s | RPE 4–6 |
| 2 | Hörst, intro hangboard video | 2021 | https://trainingforclimbing.com/video-intro-to-hangboard-training-for-finger-strength-and-endurance/ | 3–5 | — | 10–15s | — | 60s | basso |

**Validazione:** valori nel JSON (`sets: 5, work_seconds: 10, rest: 90`) tutti plausibili ✅

**video_url:** `null` — `[Hörst intro hangboard T4C YouTube — da trovare ID]`

---

## 13. one_arm_hang_assisted

**Protocollo:** One-arm hang con assistenza — Cameron Hörst advanced protocol

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------| 
| 1 | Cameron Hörst, T4C advanced video | 2020 | https://trainingforclimbing.com/advanced-hangboard-training-technique/ | 3–5 | — | 5s | — | 180s | bodyweight o leggero assist |
| 2 | Lattice Training | 2022 | https://www.climbing.com/skills/lattice-hangboarding-part-2/ | — | — | — | — | — | "single arm with pulley assist" |

**Nota:** Cameron Hörst: "start con sling di assistenza, poi progredire verso bodyweight, poi aggiungere peso nella mano libera". Appropriato solo per climbers ≥5.13/8a.

**Validazione:** valori nel JSON plausibili ✅

**video_url:** `null` — `[Cameron Hörst one-arm hangboard YouTube video — da trovare ID]`

---

## 14. pinch_block_training

**Protocollo:** Pinch block hangs / loaded pinch — allenamento presa a pizzico

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | grip |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|------|
| 1 | Hörst, T4C (menziona pinch) | 2022 | https://trainingforclimbing.com/4-fingerboard-strength-protocols-that-work/ | 2–4 | — | 7–10s | — | 180s | 80–90% MVC | pinch |
| 2 | Hooper's Beta | 2022 | https://www.hoopersbeta.com/library/hangboarding-routine-training-for-climbing | 2–4 | — | 7–10s | — | 180s | alto | pinch |

**Validazione:** campo `grip: "pinch"` ✅ nel brief — verificare JSON

**video_url:** `null`

---

## 15. lopez_subhangs

**Protocollo:** López SubHangs — long submaximal hangs per endurance

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s | intensity | edge_mm |
|---|-------|------|-----|------|------|--------|-----------|-----------|-----------|---------| 
| 1 | strengthclimbing.com (SubHangs) | 2020 | https://strengthclimbing.com/eva-lopez-subhangs-climbing-endurance-protocol/ | 4–8 | — | 20–45s | — | 30–120s | 55–85% MVC | 14–20mm |
| 2 | GitHub hangboard exercises README | 2020 | https://github.com/8cH9azbsFifZ/hangboard/blob/main/exercises/README.md | 4–8 | — | 20–45s | — | 30–120s | 55–85% | 14–20mm |

**Note chiave:**
- "Choose edge between 14–20mm and load so you can hang 20–45 seconds"
- Rest: 30s → 2 min tra set (progressione: inizia con rest lungo, accorcia nel tempo)
- Solo MAW version per climbers avanzati
- Attenzione: long hangs >30s stressano molto le spalle → warm up spalle essenziale
- Il rest progressivamente decrescente nel ciclo è caratteristica specifica del protocollo (non modellabile con un valore fisso)

**Validazione campi brief:**
- `sets: 5` ✅ (range 4–8)
- `work_seconds: 30` ✅ (basso del range 20–45)
- `rest_between_sets_seconds: 60` ✅ (basso del range 30–120)
- `edge_mm: 22` ⚠️ (range letteratura 14–20mm — 22mm è fuori range; considerare 18mm come valore centrale)

**video_url:** `null` — `[da cercare: Eva López SubHangs YouTube]`

---

## 16. critical_force_test

**Protocollo:** Test di forza critica — Lattice / Giles et al. 2019

| # | Fonte | Anno | URL | sets | reps | work_s | rest_rep_s | rest_set_s |
|---|-------|------|-----|------|------|--------|-----------|-----------| 
| 1 | Giles et al., Int J Sports Physiol Perf | 2019 | https://journals.humankinetics.com/view/journals/ijspp/14/7/article-p954.xml | 1 test | fino a failure | 7s | 3s | — |
| 2 | strengthclimbing.com (endurance repeaters) | 2021 | https://strengthclimbing.com/endurance-repeaters/ | 1 | fino a failure | 7s | 3s | — |
| 3 | Lattice Training (performance metrics) | 2025 | https://latticetraining.com/blog/what-is-the-number-1-measure-of-performance-for-sport-climbers/ | 1 | fino a failure | 7s | 3s | — |

**Protocollo esatto (Giles et al.):**
- Edge: 20mm Lattice standard, half crimp
- Carichi: 80%, 60%, 45% dell'MVC-7 → 3 test separati (giorni diversi)
- Si esegue 7s on/3s off fino al failure a ciascun carico
- Dalla curva iperbolica del tempo al failure si ricavano CF e W'

**Validazione:**
- Protocollo completo richiede lab/forza-metro — nel nostro contesto: test semplificato
- `work_seconds: null` ✅ (durata variabile, fino a failure)
- `rest_between_reps_seconds: 3` ✅
- `edge_mm: 20` ✅
- `grip: "half_crimp"` ✅

**video_url:** `null`

**Paper di riferimento (parzialmente accessibile online):**
> Giles D, Chidley JB, Taylor N et al. (2019). *The Determination of Finger-Flexor Critical Force in Rock Climbers*. International Journal of Sports Physiology and Performance, 14(7):954–961.
> DOI: https://doi.org/10.1123/ijspp.2018-0702

---

## 17. med_test — Maximum Effort Duration Test

**Protocollo:** MED Test — Lattice, test di endurance dito

| # | Fonte | Anno | URL | note |
|---|-------|------|-----|------| 
| 1 | Lattice Training / Zlagboard reference | 2020 | https://www.climbing.com/skills/lattice-hangboarding-part-2/ | "to-failure long duration hang — collecting data for years" |
| 2 | strengthclimbing.com (SubHangs / Endurance) | 2020–2021 | https://strengthclimbing.com/eva-lopez-subhangs-climbing-endurance-protocol/ | hang a carico fisso fino a failure, record tempo totale |

**Protocollo semplificato (pratico):**
- 45% del MVC-7 su 20mm half crimp
- Hang continuo (non intermittente) fino a failure
- Record: secondi totali = MED score

**Nota:** Lattice in passato usava leaderboard ma ora non lo raccomanda più come metrica principale. Rimane utile come benchmark endurance di base.

**video_url:** `null`

---

---

## 📚 Libri — Stato Accesso Online

### Verifica effettuata (sessione 2, 2026-02-20)

| # | Titolo | Autore | Anno | Stato online | Link verifica | Note |
|---|--------|--------|------|--------------|---------------|------|
| 1 | **Training for Climbing** (3rd ed.) | Eric Hörst | 2016/2022 | ⚠️ **Accesso limitato** | https://archive.org/details/trainingforclimb0000hors_edi03 | Su Internet Archive ma richiede login + prestito digitale (come biblioteca online). Serve account gratuito. ISBN: 9781493017614 |
| 2 | **The Rock Climber's Training Manual** | Mark & Mike Anderson | 2014 | ⚠️ **Accesso limitato** | https://archive.org/details/rockclimberstrai0000ande | Stessa situazione: archive.org, login richiesto. ISBN: 9780989515610 |
| 3 | **9 out of 10 Climbers** | Dave MacLeod | 2009 | ❌ Non trovato online | — | Da acquistare |
| 4 | **Logical Progression** | Steve Bechtel | 2020 | ❌ Non trovato online | — | Da acquistare su climbstrong.com |
| 5 | **Gimme Kraft!** | Peter Bührmann | 2013 | ❌ Non trovato | — | Fonte tedesca, meno urgente |

**Come accedere a archive.org:**
1. Creare account gratuito su https://archive.org/account/signup
2. Cercare il titolo
3. Cliccare "Borrow for 1 hour" (prestito digitale gratuito)
4. Leggere online nel browser (no download per PDF)

> **Nota legale:** Scribd ha copie non autorizzate — sconsigliato come fonte per questo progetto. Internet Archive è legale (controlled digital lending).

### 📄 Paper Scientifici Accessibili

| # | Titolo | Autore/i | Anno | DOI / URL | Accesso |
|---|--------|----------|------|-----------|---------|
| 1 | Comparison of three hangboard training programs | E. López-Rivera | 2016 | DOI: 10.1080/19346182.2012.716061 | Parziale |
| 2 | Determination of Finger-Flexor Critical Force | Giles et al. | 2019 | DOI: 10.1123/ijspp.2018-0702 | Parziale |
| 3 | Finger Strength Training for Climbing: A basic guide | E. López-Rivera | 2021 | https://www.researchgate.net/publication/362068736 | ✅ Gratuito su ResearchGate |

---

## 🔧 Todo — Azioni Ancora Necessarie

| Task | Priorità | Stato | Note |
|------|----------|-------|------|
| **Applicare correzione work_seconds a `min_edge_hang`** | ⭐⭐⭐ Alta | 🔲 Da fare | 7s → 12s (Hörst 2022 fonte diretta) |
| **Verificare struttura `density_hangs`** | ⭐⭐⭐ Alta | 🔲 Da fare | 10/10 non canonico; reale = 30–40s near failure |
| **Verificare sets `max_hang_5s`** | ⭐⭐ Media | 🔲 Da fare | Ridurre da 6 a 5 |
| Validare struttura rest in `max_hang_10s` (intra vs inter) | ⭐⭐ Media | 🔲 Da fare | Hörst: 3 min tra hang, 5 min tra set |
| Trovare YouTube ID Cameron Hörst 7/53 | Alta | 🔲 Da fare | T4C channel |
| Trovare YouTube ID 7/3 Repeater video Cameron Hörst | Alta | 🔲 Da fare | T4C channel |
| Trovare YouTube Lattice hangboard tutorial (Tom Randall) | Alta | 🔲 Da fare | Canale Lattice Training |
| Trovare YouTube C4HP Tyler Nelson density hangs | Media | 🔲 Da fare | Canale C4HP |
| Trovare YouTube Eva López SubHangs / MaxHangs | Media | 🔲 Da fare | YouTube diretto |
| Accedere a "Training for Climbing" su archive.org | Alta | 🔲 Da fare | Richiede account gratuito — istruzioni sopra |
| Accedere a RCTM su archive.org | Alta | 🔲 Da fare | Stessa procedura |

---

## 🔗 Conversione loading pin (una mano) → max hang (due mani) — A266

**Perché serve.** L'asse `finger_strength` dell'assessment è tarato su
`_FINGER_BENCHMARK`, cioè sul **carico totale di un max hang a due mani** diviso
il peso corporeo. Chi si allena e si testa su loading pin registra invece
`lp_max_lift_5s_left/right_kg`: un **carico esterno sollevato con una mano**.
Fino ad A266 quei numeri erano illeggibili per l'assessment e l'asse ripiegava
sulla stima da grado — anche per la beta tester che il loading pin lo usa per
necessità (limitazione alla spalla, vedi `beta_feedback.md` FB-6).

**Costante adottata:** `LP_ONE_ARM_TO_TWO_HAND = 1.85`
(`backend/engine/assessment_v1.py`), applicata alla **media** delle due mani.

**Non è un coefficiente inventato: tre fonti indipendenti convergono.**

| # | Fonte | Cosa dice | Rapporto due mani / una mano |
|---|-------|-----------|------------------------------|
| 1 | `_FINGER_BENCHMARK` (interno, già in uso) | 8a lead → carico totale **1,40 × BW** su due mani | — |
| 2 | Dataset one-arm Lattice Training, 20 mm, 7–10s | V8–V9 (≈ 8a lead) → **0,73–0,79 × BW** su un braccio | 1,40 / 0,76 = **1,84** |
| 3 | Letteratura sul *bilateral deficit* nei climber | rapporto due braccia / un braccio riportato in **1,6–2,0** (< 2,0 perché un arto isolato esprime più forza di quanto ne esprima come metà di uno sforzo bilaterale) | **1,6–2,0** |

Il valore che cade dal nostro benchmark (1,84) sta dentro il range della
letteratura e vicino al centro. Arrotondato a **1,85**. Conseguenza voluta: un
atleta che si testa su pin e uno che si testa su hangboard atterrano sullo
stesso punteggio d'asse — le due tabelle restano reciprocamente coerenti.

**Bound di plausibilità:** `LP_MAX_PLAUSIBLE_BW_RATIO = 1.5`. Il dataset Lattice
mette **V17** — il boulder più duro mai salito — a 1,18 × BW su un braccio. Oltre
1,5 non è un climber, è un errore di inserimento (peso totale invece del carico,
libbre al posto dei kg): il valore viene **scartato con un warning**, non usato
per saturare l'asse. Scartare è deliberato — è la lezione di [B321], dove uno
zero silenzioso valeva "principiante" invece di "non lo sappiamo".

**Precedenza:** se esiste un `max_hang_*` misurato, vince quello. Il pin viene
convertito solo come fallback: una misura diretta nell'unità del benchmark è
sempre preferibile a una convertita.

**Fonti:**
- Lattice Training — dataset forza dita per grado (one-arm 20 mm):
  https://latticetraining.com/2-arm-fs-test/ e la ricostruzione pubblica del
  dataset in https://wmgclimbing.wordpress.com/2024/03/10/approximating-lattices-finger-strength-data-set/
  (V4 49% → V17 118% del peso corporeo, incrementi 6%/grado sotto V11, 4% sopra V14)
- Handedness, Bilateral, and Interdigit Strength Asymmetries in Male Climbers —
  https://pubmed.ncbi.nlm.nih.gov/37678830/ (asimmetria media fra le mani 4,1%,
  motivo per cui si usa la **media** e non la somma)
- Reliability of finger strength assessment methods in climbing: a systematic review —
  https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1650198/full

**⚠️ Limite noto, da rivedere se arrivano dati migliori.** La tabella one-arm
Lattice per V11–V14 è **interpolata** dall'autore della ricostruzione, non
pubblicata da Lattice; e l'intero dataset è su **atleti maschi**. La costante è
quindi solida nella fascia centrale (V4–V11, dove i dati sono diretti) e più
debole agli estremi. Se Lattice pubblica i dati grezzi, ricalibrare qui.
