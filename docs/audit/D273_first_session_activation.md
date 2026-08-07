# D273 — Perché nessuno fa la prima sessione

**Tipo:** D (audit, read-only — nessuna riga di codice di prodotto toccata)
**Data:** 2026-08-07
**Origine:** [[B326]] ha reso visibile il numero: **4 utenti su 20 hanno mai completato
una sessione**, e uno dei quattro è l'autore. Nessun terzo ne completa una da 4 mesi.
**Domanda:** che cosa succede tra «macrociclo generato» e «prima sessione», e perché
quasi nessuno attraversa quel salto.

---

## Metodo

Nessuna ipotesi creduta sulla parola. Tre fonti, tutte verificabili:

1. **Stato reale di produzione** letto da Supabase (`public.users.state`), read-only.
2. **Replay del motore** sugli stati reali: lo stato dei due iscritti del 5 agosto è
   stato caricato in un backend `file` temporaneo e fatto passare per il **router vero**
   (`GET /api/week/1` via `TestClient`), con `datetime.now()` **congelato al loro giorno
   di iscrizione** — altrimenti il planner pianifica attorno a giorni già passati e si
   guarda una settimana che quell'utente non ha mai visto. Niente è stato riscritto in prod.
3. **Sweep**: lo stesso replay ripetuto congelando *ogni* giorno della prima settimana,
   per distinguere «è capitato a loro» da «capita per costruzione».

Gli script stanno nello scratchpad di sessione (`replay_frozen.py`, `sweep_day1.py`);
sono usa-e-getta e dipendono da `.env`, quindi non sono stati committati.

---

## Finding 1 — La prima cosa che l'app offre non è una cosa che si può fare adesso

### Jason (`e60d7a0c`, il primo iscritto organico da Reddit)

Onboarding completato **mercoledì 5 agosto alle 07:30:56**. Il suo piano è stato generato
**alle 07:31:14 — 18 secondi dopo** (`_prev_week_plan.generated_at`, dato reale, non
ricostruito). Conteneva esattamente tre sessioni:

| giorno | sessione | durata | dove |
|---|---|---|---|
| **mer 05/08** — il giorno in cui si è iscritto | **Prehab Maintenance (Daily)** | 20 min | casa |
| gio 06/08 | Complementary Conditioning (Carries + Crawls + TGU) | 35 min | casa |
| sab 08/08 | Boulder Circuit (Gym) | 85 min | palestra |

Un tizio arriva da Reddit su un'app di allenamento per arrampicata, obiettivo 7B → 7C
boulder, dichiara 5 sere disponibili. Completa dodici step di onboarding. La prima cosa
che l'app gli mette davanti sono **venti minuti di CARs di spalla, cuffia dei rotatori
ed eccentrici di gomito, in salotto**. La prima volta che tocca una presa è **sabato,
tre giorni dopo**.

Il piano **non è sbagliato**: rispetta le sue disponibilità (mercoledì e giovedì li ha
dichiarati *casa*, e a casa ha manubri, elastico e kettlebell — nessuna attrezzatura da
arrampicata), rispetta l'attrezzatura e il `target_training_days`. È corretto e inerte.

### selias (`f8ff8569`)

Onboarding completato **mercoledì 5 agosto alle 19:44**. Piano per quella stessa sera:
**Boulder Circuit, 85 minuti, in palestra.** Alle 19:44. Il giorno dopo: Technique Focus,
90 minuti. Il giorno dopo ancora: altri 85 minuti.

Specularmente allo stesso problema: la prima proposta è arrivata nel momento di massima
motivazione — i minuti subito dopo l'onboarding — ed era **inagibile**.

### Non è sfortuna: è la struttura

Sweep del giorno di iscrizione su tutti e 7 i giorni della prima settimana, a parità di
profilo reale:

| iscritto di… | Jason (2 giorni casa, 2 palestra) | selias (tutti palestra) |
|---|---|---|
| lun | Prehab 20 min — **1 giorno** al 1° climbing | vuoto — 1 giorno |
| mar | Boulder Circuit 85 min | Boulder Circuit 85 min |
| **mer** ← il loro | **Prehab 20 min — 3 giorni** | **Boulder Circuit 85 min** |
| gio | Prehab 20 min — 2 giorni | Boulder Circuit 85 min |
| ven | vuoto — 1 giorno | Boulder Circuit 85 min |
| sab | Boulder Circuit 85 min | Boulder Circuit 85 min |
| dom | vuoto — mai in settimana | Boulder Circuit 85 min |

Per il profilo di Jason, **4 giorni su 7 danno un day-1 che non è arrampicata** e 2 danno
un giorno vuoto. Ha pescato la casella peggiore, ma le caselle buone sono una minoranza.

### Il fatto strutturale sotto

Distribuzione delle durate del catalogo (`time_budget.target_duration_min`, 35 sessioni):

| | ≤20 | 21-40 | 41-60 | 61-80 | >80 |
|---|---|---|---|---|---|
| sessioni | 1 | 15 | 5 | 6 | 8 |

Ma se si guardano **solo le sessioni che coinvolgono la parete**, sono sei e la più corta
è **70 minuti** (`easy_climbing_deload`, che è una sessione di scarico). Quelle vere stanno
a **85-100 minuti**.

> **Non esiste nel prodotto una sessione di arrampicata corta.** Alla domanda «sono dentro,
> ho trenta minuti e voglio provare questa cosa» il motore non ha nessuna risposta.

---

## Finding 2 — Anche volendo richiamarli, non c'è un canale

Grep sull'intero backend: l'unico invio di notifiche è `backend/api/notifications.py`,
che manda un messaggio **Telegram a Daniele** quando qualcuno si iscrive. Il service worker
(`frontend/public/sw.template.js`) **non ha un handler `push`**. Non c'è email
transazionale, non c'è push, non c'è promemoria.

Combinato col Finding 1: il piano di Jason rimandava la prima sessione vera a **sabato**,
e **nel prodotto non esiste niente che sabato gli dicesse di tornare**. La sua unica visita
è stata quella dell'iscrizione, e in quella visita l'app non aveva niente su cui potesse agire.

Vale per tutti: `quote_history` ha **una sola voce** per entrambi (un id di citazione per
giorno di apertura) → **entrambi hanno aperto l'app un giorno solo, quello dell'iscrizione**.
Confermato da Clerk: `last_active == created` per tutti e due.

---

## Cosa è stato escluso, con la prova

- **Paywall.** Ipotesi seria: `/today` fa `if (!canInteract) router.push("/subscribe")` su
  ogni azione. Ma `subscription_guard` per un trial locale con `trial_end` futuro ritorna
  `can_interact: True` (`subscription_guard.py:279`), e le loro righe sono `trialing` fino
  al 20/08. **Non sono stati messi davanti a un paywall.**
- **CTA nascosta.** `session-card.tsx` ha sia il bottone «Start session» sia un FAB visibile
  senza espandere la card. Il problema non è trovare il pulsante.
- **`/today` rotto.** La pagina ha stati vuoti curati (`pre_start` / `offday` / `empty_week`,
  A-ACTIVATION-TIMING). Non è una pagina bianca.
- **Onboarding non completato.** Entrambi hanno macrociclo, assessment, availability,
  equipment. L'onboarding funziona: è quello **dopo** che non converte.

---

## Osservazione secondaria — il piano di Jason non è più nella cache viva

`week_plans` è **vuoto** e `current_week_plan` è `None`, mentre il piano generato alle
07:31:14 sta in **`_prev_week_plan`**. `_prev_week_plan` viene scritto solo da
`invalidate_week_cache()` (`deps.py:65`), che sposta lì il piano corrente — quindi dopo la
generazione qualcosa ha invalidato la cache e la voce della settimana corrente è sparita
anche da `week_plans` (i due filtri di invalidazione la preserverebbero: `k < oggi` e
`k <= lunedì corrente` la tengono entrambi; la rimuove il filtro `k < new_start_date` di
`macrocycle.py:152`). Il 5/08 alle 10:17 uno script ha riscritto in massa gli stati per la
remediation [[B321]].

**Non è (ancora) un danno**: al primo `/today` il piano si rigenera e `merge_prev_week_sessions`
ripesca da `_prev_week_plan`. Ma la presenza di `_prev_week_plan` **è essa stessa la prova
che quel `/today` non è mai arrivato**. Va tenuto d'occhio, non trattato come perdita di dati.

---

## Dove intervenire (proposte, non decise)

Ordinate per rapporto tra effetto atteso e rischio. **Nessuna implementata**: toccano
`planner_v2` / catalogo, quindi passano dallo STOP-gate.

1. **Una prima sessione che si può fare subito.** Al primo `/today` dopo l'onboarding,
   offrire una sessione corta e di arrampicata, indipendente dal giorno e dalla fase — un
   «benvenuto, prova questa» da 25-35 minuti. Oggi il catalogo non ce l'ha: la più corta
   con parete è 70 minuti. È il buco più grande e il più chiudibile (voce di catalogo +
   un ramo nel planner per la settimana 1).
2. **Non aprire con la prehab.** Se il giorno 1 di un utente nuovo cade su uno slot casa,
   il piano gli dà cuffia dei rotatori. Regola candidata: nella prima settimana la prima
   sessione proposta è la prima **di arrampicata** disponibile, e la prehab si accoda.
3. **Dire quando si arrampica.** Se la prima sessione vera è fra tre giorni, `/today` deve
   dirlo esplicitamente («la prima sessione in palestra è sabato»), non lasciarlo dedurre.
   `nextSessionInfo` esiste già ed è calcolato — oggi lo mostra solo negli stati vuoti.
4. **Un canale di ritorno.** Senza push né email, ogni piano che rimanda la prima sessione
   di più di poche ore è una scommessa sul fatto che l'utente si ricordi da solo. È il
   prerequisito che rende utili le prime tre, e l'unico che richiede infrastruttura nuova.

---

## Nota GTM

Questo è il motivo per cui **GTM-05 (il post su r/climbharder) va fatto dopo, non prima.**
Il canale non è il collo di bottiglia più stretto: su 20 registrati 4 hanno mai completato
una sessione, e l'unico terzo con uso vero (`ckb.palmer`, 20 sessioni) si è fermato il
7 aprile. Mandare traffico su questo salto lo moltiplica per zero.
