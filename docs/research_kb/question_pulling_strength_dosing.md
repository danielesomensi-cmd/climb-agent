# Domanda per il KB — dosaggio e collocazione della forza di trazione con sovraccarico

> **Come usarla:** incollare la sezione "PROMPT" nel progetto **"knowledge climbing"** su claude.ai (che ha accesso a Hörst, Lattice, Eva López, Tyler Nelson/C4HP, Anderson, Bechtel, MacKenzie, Michailov, Giles…). Segue il processo di `docs/audit_workflow.md` Step 2, ma è una domanda **mirata**, non un audit completo.
>
> **Origine:** [[D263]] — Daniele ha notato di non vedere quasi mai trazioni con sovraccarico né bloccaggi nel piano. La verifica sul suo stato di produzione ha confermato il fenomeno e ne ha isolato le cause. Prima di cambiare il motore serve sapere **qual è la risposta giusta dal punto di vista metodologico**, perché le due opzioni implementative (collegare una sessione dedicata vs. modificare i template esistenti) producono dosi molto diverse.

---

## Cosa sappiamo già (misurato, non ipotizzato)

**Comportamento attuale del motore**, verificato sullo stato di produzione di Daniele il 2026-07-29:

- Esiste una sessione dedicata `pulling_strength_gym` con **tre blocchi** di tirata (trazione con sovraccarico, bloccaggio isometrico, typewriter). **Non è nel pool di nessuna fase**: il macrociclo non può schedularla mai.
- Restano due sole fonti di lavoro di tirata, entrambe **un blocco singolo** dentro sessioni che hanno altro come focus: `strength_long.pulling_compound` (solo in `strength_power`) e `limit_boulder_gym.supplementary_pulling` (opzionale).
- Sul macrociclo di Daniele (12 settimane: base 2, strength_power 4, power_endurance 3, performance 2, deload 1) **solo 6 settimane possono ospitare un blocco di tirata**. In `base`, `power_endurance` e `deload`: **zero**.
- Quando il blocco c'è, la rotazione funziona: simulando 16 settimane con seed di varietà e recenza reali → `lock_off_isometric` 4/16, `weighted_chinup` 4/16, `one_arm_pullup_assisted` 4/16, `typewriter_pullup` 2/16, `pullup` 2/16. La trazione zavorrata "pura" (`weighted_pullup`) esce di rado perché condivide il gruppo di recenza con altri cinque esercizi.

**I pesi di dominio si adattano al profilo, il pool di sessioni no.** `_adjust_domain_weights` alza il peso degli assi deboli (<50) e abbassa quelli forti (>75). Per Daniele: `pulling_strength` 0.25 → 0.21 in strength_power e 0.05 → 0.02 in performance; `technique` 0.10 → 0.19 e 0.25 → 0.34. Ma l'appartenenza di una sessione al pool di fase è **statica**: uno scalatore con tirata debole riceverebbe la stessa quantità di lavoro (quasi nulla) di uno con tirata massimale.

**Profilo dell'utente di riferimento (Daniele):**

| | valore |
|---|---|
| assi (0-100) | finger_strength **100**, pulling_strength **100**, power_endurance 54, endurance 52, technique **30** |
| trazione zavorrata | 1RM stimato 127.8 kg totali su 77 kg di peso → **+51 kg esterni, ratio 158%** |
| sospensione | 122 kg totali, 20 mm half-crimp, 7 s |
| obiettivo | 8a → 8a+ lead (deadline 2026-08-09), boulder 7C |

**Cosa dice già il nostro KB** (`backend/coach/knowledge/L3/03_pulling_strength.md`), da confermare o correggere:

- la tirata è il secondo predittore di prestazione dopo la forza delle dita (MacKenzie 2020);
- per l'avanzato: trazioni zavorrate + bloccaggi a EL 8-9 (87-93% 1RM), 2-5 rip, 4-5 serie, 3-5 min di recupero;
- quando la tirata è l'asse debole: **1-2 sessioni a settimana**, con volume di sospensioni ridotto, e riverifica dopo 4-6 settimane.

Quindi il KB prescrive 1-2 **sessioni** settimanali nel caso "asse debole", mentre il motore offre al massimo **un blocco** dentro una sessione mista, e solo in 4 settimane su 12.

---

## PROMPT (da incollare nel progetto "knowledge climbing")

Sei un esperto di scienza dell'allenamento per l'arrampicata, con accesso alla letteratura del knowledge base di questo progetto (Hörst, Lattice, Eva López, Tyler Nelson/C4HP, Anderson, Bechtel, MacKenzie, Michailov, Giles, Consuegra, Matros e gli altri).

Ho una domanda **mirata** su dosaggio e collocazione periodica della forza di trazione con sovraccarico (trazioni zavorrate, bloccaggi isometrici, varianti monobraccio) in un piano periodizzato per arrampicata. Non serve un audit completo: servono risposte utilizzabili per una decisione implementativa.

**Contesto tecnico.** climb-agent è un motore deterministico che genera piani settimanali. Il macrociclo ha 5 fasi (base → strength_power → power_endurance → performance → deload). Ogni fase ha un pool di sessioni ammesse e dei pesi per dominio, questi ultimi già corretti in base al profilo dell'utente (gli assi deboli salgono, i forti scendono). Oggi il lavoro di trazione pesante esiste **solo** come singolo blocco dentro sessioni miste, e solo nella fase strength_power (più un blocco opzionale in una sessione di boulder al limite). Su un macrociclo di 12 settimane, 6 settimane non ne hanno alcuna possibilità e 3 fasi su 5 ne sono del tutto prive. Esiste una sessione dedicata di sola forza di trazione (3 blocchi) che però non è collegata a nessuna fase.

**Utente di riferimento:** Daniele, lead climber, 77 kg, obiettivo 8a → 8a+ (Fontainebleau), boulder 7C. Profilo 0-100: dita 100, trazione 100, power endurance 54, resistenza 52, tecnica 30. Trazione zavorrata 1RM stimato +51 kg esterni (127.8 kg totali, ratio 158%). Sospensione 122 kg a 20 mm half-crimp 7 s.

Rispondi a queste domande, ognuna con il riferimento alla fonte e, dove la letteratura è incerta o divergente, dicendolo esplicitamente invece di scegliere per me:

**1. Collocazione.** In quali fasi di un macrociclo per arrampicata la forza di trazione con sovraccarico dovrebbe essere allenata, e in quali è corretto ometterla? In particolare: ha senso che base, power endurance e performance ne siano completamente prive?

**2. Mantenimento e detraining.** Qual è la dose minima per **mantenere** la forza massima di trazione già acquisita, e in quanto tempo si perde senza stimolo? Il nostro KB cita la perdita capillare a 2-3 settimane per la resistenza; qual è l'equivalente per la forza massima di trazione? Otto settimane su dodici senza alcun lavoro di trazione sono un problema per un atleta a +51 kg, o la trazione richiesta dall'arrampicata stessa (boulder al limite, vie di progetto) basta come mantenimento?

**3. Il caso "asse già massimale".** Il nostro assessment dà a Daniele 100/100 sulla trazione, e i pesi di dominio abbassano di conseguenza il lavoro di tirata a favore della tecnica (30/100). È metodologicamente corretto **azzerare quasi del tutto** il lavoro di trazione per un atleta che l'ha come punto di forza, o esiste un pavimento di mantenimento sotto il quale non si dovrebbe scendere neanche per un asse massimale? Detto altrimenti: la nostra regola "asse forte → meno lavoro" è giusta, o è giusta solo fino a una certa soglia?

**4. Dose ed esercizi.** Per un avanzato con questi numeri, quale sarebbe la prescrizione corretta nelle fasi in cui il lavoro va fatto: quante sedute a settimana, quante serie e ripetizioni, a quale percentuale di 1RM, quanto recupero? E che rapporto dovrebbero avere trazioni zavorrate, bloccaggi isometrici e progressioni monobraccio — sono intercambiabili o coprono qualità distinte che vanno programmate separatamente?

**5. Sessione dedicata o blocco dentro una sessione mista?** Questa è la domanda implementativa vera. Due opzioni: (a) collegare la sessione dedicata di sola forza di trazione (3 blocchi, alta intensità) a uno o più pool di fase, il che aggiunge una seduta "dura" e va in competizione con boulder al limite e contact strength per il tetto settimanale di giorni duri; (b) lasciare tutto dentro le sessioni miste e semmai aggiungere un blocco di tirata anche alle sessioni di base e power endurance. Quale delle due è più difendibile dal punto di vista della letteratura, e perché? Ci sono controindicazioni note nell'accorpare trazione pesante e boulder al limite nella stessa settimana o nella stessa seduta?

**6. Interferenza.** Il lavoro pesante di trazione confligge con la sospensione massimale (già limitata dal motore a una seduta a settimana) o con il boulder al limite? Quali distanze minime fra stimoli, e quale ordine intra-settimanale?

**7. Verdetto sul caso concreto.** Per Daniele così com'è oggi — 2 settimane alla fine del macrociclo, in fase performance, con tecnica a 30 come vero punto debole — il comportamento attuale del motore (praticamente nessuna trazione pesante) è **corretto**, o gli sta facendo perdere qualcosa? Se è corretto per lui ma sbagliato in generale, dillo chiaramente: mi serve sapere se sto guardando un bug o una scelta giusta che sembra un bug.

Per ogni raccomandazione indica la severità: **CRITICO** (il piano è sbagliato o rischioso), **IMPORTANTE** (migliorerebbe in modo significativo), **NICE** (ottimizzazione). E se una risposta dipende da un dato che non ti ho dato, chiedimelo invece di assumerlo.

---

## Cosa farne dopo

La risposta decide fra tre esiti, tutti già istruiti lato codice:

1. **Va bene così** → chiudere [[D263]] come won't-fix, annotando la motivazione metodologica.
2. **Serve la sessione dedicata** → collegare `pulling_strength_gym` ai pool di fase indicati dalla risposta (`_SESSION_POOL` in `macrocycle_v1.py`), verificando l'effetto sul tetto di giorni duri.
3. **Serve un blocco nelle fasi scoperte** → aggiungere un modulo di tirata alle sessioni di `base` e `power_endurance`, sul modello di `strength_long.pulling_compound`.

In tutti e tre i casi vale la regola del progetto: `macrocycle_v1.py` è modulo ad alto rischio → analisi, STOP, OK esplicito, poi implementazione.
