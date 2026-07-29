# D263 — i 3 dati richiesti dal KB + audit del punto 5

> Risposta ai tre dati mancanti chiesti in testa alla risposta del KB, verificati sul codice e sullo stato di produzione di Daniele (2026-07-29). Più l'audit del punto 5, che il KB indicava come il più preoccupante.

---

## Dato 1 — Giorni allenabili e tetto giorni duri

**L'assunzione del KB era conservativa: la realtà lascia molto più spazio.**

| | assunto dal KB | reale |
|---|---|---|
| giorni allenabili | 3-4 | **7** (tutte le sere, slot `evening`) |
| tetto giorni duri | 2 | **4** (`planning_prefs.hard_day_cap_per_week`) |
| giorni target | — | **7** (`target_training_days_per_week`) |

Il default del planner è 3 giorni duri, ma `hard_cap = planning_prefs.get("hard_day_cap_per_week", 3)` → per Daniele vale **4**. Le sue palestre: Bkl (lun), Work (ven), Cocque (sab+dom), più le sere infrasettimanali.

**Conseguenza sulla §5 della risposta:** l'argomento «aggiungere una quarta seduta dura è impossibile senza togliere qualcosa» **non si applica a questo utente**. Con 7 giorni disponibili e tetto 4, l'opzione (a) è praticabile *per lui*. Resta valido come vincolo generale per utenti con 3-4 giorni, che sono probabilmente la maggioranza — quindi la raccomandazione «(b) come default, (a) condizionata» regge, ma la condizione dovrebbe includere anche la **capienza settimanale reale**, non solo il punteggio dell'asse.

## Dato 2 — Macrocicli dopo il 2026-08-09

**Nessuno.** Il macrociclo corrente (2026-05-18 → 2026-08-09) è l'ultimo: `macrocycle_history` contiene un solo ciclo chiuso (2026-02-23 → 2026-05-17) e non esiste alcun ciclo successivo pianificato. La deadline dell'obiettivo coincide con la fine del ciclo (2026-08-09, 8a+).

**Conseguenza:** per Daniele l'urgenza è **nulla** — mancano 11 giorni, è in taper. Il fix conta per il motore e per il prossimo ciclo, non per lui adesso. Conferma il verdetto §7.

## Dato 3 — La scala 0-100 satura? **Sì, ma con una sfumatura che cambia la lettura**

La scala **satura** (`_clamp` a 100), ma **non è un percentile**: è **relativa all'obiettivo**. Il punteggio è `(ratio_atleta / benchmark_del_grado_obiettivo) × 100`.

Per Daniele: ratio 1.660 (127.8 kg / 77 kg), benchmark 8a+ = 1.65 → punteggio grezzo **100.6**, clampato a 100.

**Quindi "100/100" non significa "molto più forte del necessario": significa "esattamente al requisito, con margine zero"** — è 1.01× il benchmark. Questo *rafforza* il punto 3c della risposta: non è un compito chiuso, è un asset esattamente sulla soglia. Un decadimento anche piccolo lo porta **sotto** il requisito per il suo obiettivo.

Nota: la presentazione lo dice già correttamente all'utente — B304 ha rietichettato il radar come "Readiness for {target}" con badge "✓ At target" al posto del 100 nudo.

**Sulla calibrazione di `_adjust_domain_weights`:** la regola è `score > 75 → −0.03`, `score < 50 → +0.05`, poi rinormalizzazione. Con una scala target-relativa e saturante, un atleta *esattamente al requisito* (100) riceve la stessa penalizzazione di uno *ampiamente sopra* (che pure verrebbe clampato a 100). La soglia non distingue "arrivato" da "abbondantemente oltre" — il che è precisamente il difetto (a) che la risposta chiama "manca il pavimento", ma aggravato dalla saturazione: **l'informazione per costruire il pavimento è già persa nel clamp**.

---

## Audit punto 5 — il difetto è una classe o un caso isolato?

**Domanda:** «peso basso → dose zero» colpisce anche altri domini?

**Metodo:** per ogni fase e per ogni asse, contate le sessioni del pool che dichiarano almeno un blocco con un dominio di quell'asse. Un asse con peso > 0 e **zero** sessioni è un dominio dichiarato ma non erogabile.

**Risultato: il difetto NON è una classe generale.** Su 30 coppie (5 fasi × 6 assi), solo **3** hanno peso > 0 e zero sessioni:

| fase | asse | peso | giudizio |
|---|---|---|---|
| power_endurance | **pulling_strength** | 0.10 | ⚠️ **il vero buco** |
| deload | pulling_strength | 0.05 | benigno — il KB stesso dice che zero in deload è difendibile |
| deload | power_endurance | 0.05 | benigno, stessa ragione |

E una copertura **sottilissima** che merita attenzione:

| fase | asse | peso | sessioni |
|---|---|---|---|
| base | pulling_strength | 0.15 | **1**, e per giunta `complementary_conditioning` (solo `available`, non primary) |

Tutti gli altri assi sono coperti da 2-11 sessioni per fase.

**Conclusione:** il problema è **specifico della trazione**, non sistemico. Escludendo il deload (benigno), i buchi reali sono due: `power_endurance` a zero e `base` a una sola sessione opzionale. Questo **riduce l'ambito del punto 5** da "audit di una classe di bug" a "il difetto è quello già isolato, confermato su un secondo fronte (base+PE)". La preoccupazione era legittima ma il perimetro è contenuto.

**Non modifica invece la severità dei punti 1-4 della raccomandazione**, che restano validi: in particolare il difetto «peso probabilistico ≠ dose garantita» resta reale anche se oggi morde su un solo asse — e l'audit mostra che morde proprio dove il peso è più basso, cioè esattamente dove il meccanismo è più fragile.

---

## Riepilogo per il KB

1. **7 giorni allenabili, tetto 4 giorni duri** → l'opzione (a) è praticabile per Daniele; la §5 va riletta con la capienza settimanale come seconda condizione oltre al punteggio d'asse.
2. **Nessun macrociclo dopo il 2026-08-09** → urgenza nulla per lui, il fix vale per il motore e il ciclo prossimo.
3. **Scala saturante e target-relativa**: 100 = "esattamente al requisito dell'obiettivo", non "molto sopra". Daniele è a 1.01× il benchmark 8a+, margine zero. Il clamp distrugge l'informazione necessaria a distinguere "arrivato" da "oltre" — il pavimento va costruito su un'altra grandezza (il ratio grezzo, che è disponibile).
4. **Punto 5**: difetto **non** sistemico. Solo `power_endurance`/`pulling_strength` (0.10, zero sessioni) e `base`/`pulling_strength` (0.15, una sola sessione opzionale). Il deload a zero è benigno.

Con questi dati si possono trasformare i punti 3-4 della raccomandazione in brief con STOP gate.
