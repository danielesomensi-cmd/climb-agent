# Domanda per il KB — vale la pena acquisire *The Climbing Bible* per i drill di tecnica?

> **Come usarla:** incollare la sezione "PROMPT" nel progetto **"knowledge climbing"** su claude.ai (che ha accesso a Hörst, Lattice, Eva López, Tyler Nelson/C4HP, Anderson, Bechtel, MacKenzie, Michailov, Giles…). Segue `docs/audit_workflow.md` Step 2, ma è una domanda **mirata**: non chiede un audit, chiede una decisione di acquisto.
>
> **Origine:** [[C264]] — il KB del coach dichiarava mancanti 23 drill di Bechtel che il motore ha in catalogo da luglio, e il coach lo ripeteva agli utenti. Corretta la nota, resta **un solo gap dichiarato** su Topic 08: il catalogo drill di Mobråten. Prima di comprare il libro (≈30 €) e spendere ~3 sessioni di estrazione come per Bechtel, vogliamo sapere **se aggiunge qualcosa che non abbiamo già**.

---

## Cosa abbiamo già (contato sul catalogo, non stimato)

**47 esercizi** con dominio `technique_*` nel catalogo del motore. Di questi, **23 sono i drill di Bechtel** (*Climb Strong: Drills Manual* pp.31-91), integrati in tre batch fra maggio e luglio 2026 e oggi tutti selezionabili dal planner.

Distribuzione per dominio dichiarato:

| Dominio | Esercizi |
|---|---|
| `technique_footwork` | 15 |
| `technique_movement` | 12 |
| `technique_body_position` | 10 |
| `technique_boulder` | 4 |
| `technique_lead` | 3 |
| `technique_constraint` | 3 |
| `technique_relaxation` | 1 |

**I 23 di Bechtel**, per focus:

- **Piedi (6):** Five Step, Foot Flyaways, Foot to Hand, Hard Target, Surface of the Shoe, Talon Feet
- **Posizione del corpo (6):** Applied Strength, Banded Climber, Barn Door 2000, Diagonal Drill, Hips First, Matchy Matchy
- **Movimento / momentum (7):** Climb It Backwards, Contrast Bouldering, Deadpoint Roll-Through, Hop and Skip, Smooth Is Fast, The Bump, Trust the Eyes
- **Reattività / esplosività (3):** Green Light Red Light, Pogo, Throwing The Shoe
- **Vincolo (1):** Single Leg Climbing

**Gli altri 24**, dal set Hörst Ch.4 / Anderson & Anderson / Matros (via Consuegra Ch.8) e da lavoro nostro: silent feet, sticky feet, foothold stare, tap and place, heel hook specific, flag practice, hip rotation, twist lock, straight arms, hover hands, no readjust, slow climbing, sloth monkey, downclimbing, freeze drill, one hand climbing, three limb drill, breathing awareness, timed route preview, fall practice, limit bouldering, spray wall limit, gym technique boulder drills, warmup easy boulders.

**Cosa il nostro KB dice già di Mobråten** (`docs/research_kb/01_performance_determinants.md` §4.3, ricavato da recensioni, non dal libro): metodologia della nazionale norvegese, assessment strutturato dentro la pianificazione, capitoli di tecnica su posizione del corpo, piedi ed efficienza di movimento. L'audit (`coach_kb_v1_audit.md`) lo classifica P1, «modern European training synthesis», e segnala **un solo punto concreto**: il downclimbing dei riscaldamenti, che Mobråten «expands».

---

## Cosa ci sembra scoperto (da confermare o smentire — è la parte su cui vogliamo il tuo giudizio)

Guardando le famiglie sopra, i buchi che *sospettiamo* sono:

1. **Coordinazione e movimento dinamico moderno** — parkour-style, coordination boulder, doppio dinamico, run-and-jump: il boulder indoor degli ultimi 5 anni ne è pieno e noi abbiamo 3 soli drill "esplosivi".
2. **Tensione corporea e compressione** — abbiamo drill di posizione (flag, twist lock, hips first) ma niente di specifico su compression, tension attraverso volumi, o toe-hook attivo.
3. **Lettura e tattica di via** — 3 drill `technique_lead` e un `timed_route_preview`; niente su segmentazione del redpoint, memorizzazione di sequenze lunghe, gestione dei riposi.
4. **Placca e aderenza** — quasi nulla: `no-hands slab` è nel KB testuale ma non come esercizio di catalogo, e i drill di piedi che abbiamo sono quasi tutti pensati per strapiombo.
5. **Progressione dei drill** — i nostri sono tutti a difficoltà piatta: nessuno dice come si evolve un drill quando l'atleta lo padroneggia.

---

## PROMPT (da incollare nel progetto "knowledge climbing")

Sto decidendo se acquisire **Mobråten & Christophersen, *The Climbing Bible* (2020)** per estenderne i drill di tecnica in un motore di allenamento per arrampicata. Il libro costa ~30 € e l'integrazione mi costerebbe circa tre sessioni di lavoro (è il costo che ho sostenuto per i drill di Bechtel). Voglio una risposta che mi faccia decidere, non un riassunto del libro.

**Cosa ho già in catalogo — 47 drill di tecnica:**

- 23 dal *Climb Strong: Drills Manual* di Bechtel (pp.31-91), completo: 6 di piedi (Five Step, Foot Flyaways, Foot to Hand, Hard Target, Surface of the Shoe, Talon Feet), 6 di posizione del corpo (Applied Strength, Banded Climber, Barn Door 2000, Diagonal Drill, Hips First, Matchy Matchy), 7 di movimento/momentum (Climb It Backwards, Contrast Bouldering, Deadpoint Roll-Through, Hop and Skip, Smooth Is Fast, The Bump, Trust the Eyes), 3 di reattività (Green Light Red Light, Pogo, Throwing The Shoe), 1 di vincolo (Single Leg Climbing).
- 24 dal set Hörst Ch.4 / Anderson & Anderson / Matros: silent feet, sticky feet, foothold stare, tap and place, heel hook drill, flag practice, hip rotation, twist lock, straight arms, hover hands, no-readjust, slow climbing, sloth monkey, downclimbing, freeze, one-hand climbing, three-limb drill, breathing awareness, timed route preview, fall practice, limit bouldering, spray wall limit, gym technique boulder drills, warm-up easy boulders.

**Le mie domande, in ordine di importanza:**

1. **Cosa contiene *The Climbing Bible* sui drill di tecnica che questa lista non copre?** Nomina le famiglie o i drill specifici, con il capitolo. Se la risposta onesta è "poco o niente di non ridondante", dimmelo: è un esito utile quanto l'opposto.

2. **Verifica le mie cinque ipotesi di buco** — (a) coordinazione/dinamico moderno da boulder indoor, (b) tensione corporea e compressione, (c) lettura di via e tattica di redpoint, (d) placca e aderenza, (e) progressione di un drill quando l'atleta lo padroneggia. Per ciascuna: è un buco reale nella mia copertura? Mobråten la colma? Se non la colma lui, **quale fonte lo fa meglio** (anche non libro: Lattice, Hooper's Beta, articoli)?

3. **Il downclimbing.** Il mio audit annota che Mobråten "espande" il downclimbing dei riscaldamenti rispetto a Hörst. Cosa aggiunge in concreto, e vale da solo un capitolo di integrazione?

4. **Ordine di priorità.** Ho altri tre libri non acquisiti: MacLeod *9 Out of 10 Climbers* (P1, per il framing sul lavorare le debolezze e i capitoli mentali), Ilgner *The Rock Warrior's Way* (P1, unica trattazione book-level della paura), Christophersen *Managing Injuries* (P0, riabilitazione). **Se dovessi comprarne uno solo nei prossimi due mesi, quale rende di più** per un motore che oggi ha: 47 drill di tecnica, un modulo mentale basato su Hörst + Garrido-Palomino 2023 + Mangan 2024, e un modulo infortuni basato su Schöffl + Quarmby + Hörst Ch.13?

5. **Metodologia dei drill, non solo elenco.** C'è in Mobråten una struttura su *come* si prescrive un drill — dosaggio (quanti per sessione, per quanto tempo), collocazione nel macrociclo, criteri per dire "questo drill l'hai assimilato, passa al prossimo"? Questa è la cosa che a me manca di più: i miei 47 drill sono tutti a difficoltà piatta e senza criterio di uscita.

**Come voglio la risposta:** per ogni punto, cosa dice la fonte, con riferimento (libro + capitolo/pagina, o studio + anno), e dove non c'è evidenza dillo esplicitamente invece di colmare il buco con buon senso. Se una raccomandazione dipende dal livello dell'atleta, specifica la fascia (io sto tarando su 7a-8a lead / 7A-7C boulder).

---

## Cosa faremo della risposta

- Se emergono famiglie di drill davvero scoperte → brief di catalogo `C` sul modello di C255/C256 (estrazione a batch, dedup contro i 47 esistenti, test di selezionabilità).
- Se emerge la **metodologia di progressione** (punto 5) → è più prezioso dei drill stessi: oggi il motore prescrive drill senza criterio di uscita, e sarebbe un brief di engine, non di catalogo.
- Se la risposta è "ridondante" → chiudiamo il gap Mobråten nel KB dichiarandolo **valutato e scartato**, invece di lasciarlo aperto per sempre come "not acquired". Anche questo è un esito da scrivere.
