# A270 — Demozione del gap redpoint − onsight

> **Tipo:** A (feature, correzione metodologica) · **Origine:** decisione di ricerca [[D266]] · analisi [[D272]] · chiude [[D260-P1b]]
> **Moduli:** `assessment_v1.py` **e** `macrocycle_v1.py` (⚠️ entrambi sulla lista STOP di CLAUDE.md)
> **Dipende da:** [[A269]] (`profile_source` + `profile_scoring_version`). **Non iniziare prima.**
>
> ⛔ **STOP gate.** Analisi già fatta ([[D272]]). Serve OK esplicito di Daniele prima di scrivere codice.

---

## 1. La decisione presa

Il gap redpoint − onsight è un **composito tattica/stile/testa, non una misura fisiologica** ([[D266]]). Oggi guida due assi e, attraverso la tecnica, produce **la più grande distorsione di piano** che [[D260]] abbia trovato: +7,3 pp di peso `technique` in **ogni** fase, per un atleta il cui gap largo è una scelta di stile.

Opzione scelta fra le tre di [[D272]] §2: **(c)** — tecnica esce dai pesi e dalle durate, e viene marcata `self_reported`.

**Con una precisazione decisa dopo l'analisi: la parte motore e la parte grafica si separano.** [[D272]] le aveva impacchettate; non devono esserlo. Questo brief fa **solo la parte motore**. L'asse resta disegnato sul radar con il suo numero. Grigiarlo è una decisione reversibile e indipendente, da prendere quando si saprà se [[D271]] va avanti — perché tecnica grigia + endurance `estimated` + PE senza repeater (**15 utenti su 18**) lascerebbero un iscritto nuovo con due soli assi vivi sulla pagina pubblica di acquisizione, e [[A267]] sotto i tre vertici disegna raggi invece di un poligono.

## 2. Modifiche al motore

### 2.1 `assessment_v1._compute_technique` — il gap esce

```python
def _compute_technique(grades, self_eval) -> int:
    score = 50.0 + _weakness_penalty(self_eval, "technique")
    return _clamp(score)
```

Il parametro `grades` diventa inutilizzato: **rimuoverlo dalla firma**, non lasciarlo lì a suggerire una dipendenza che non c'è.

Valori possibili: **40** (debolezza primaria fra `technique_errors`, `cant_read_routes`, `poor_body_tension`, `poor_problem_reading`, `poor_dynamic_movement`), **45** (secondaria), **50** (nessuna). Tre valori — ed è precisamente il motivo per cui non deve muovere nulla.

`profile_source.technique = "self_reported"` — quarto valore introdotto qui, definito in [[A269]] §3.1 come *«asse derivato da un solo input soggettivo e da nessun test»*.

### 2.2 `assessment_v1._compute_power_endurance` — il gap esce, il repeater resta

```python
if has_repeater:
    score = repeater_score + _weakness_penalty(self_eval, "power_endurance")
    source = "partial"
else:
    score = 50.0          # neutro esatto: nessun modificatore, nessun segnale
    source = "estimated"
```

**Perché il ramo senza repeater è 50 secco e non `50 + eval`.** Il peso di dominio ha una banda morta 50–75: a 50 esatti l'asse non muove niente. Con `eval = −8` scenderebbe a 42, cioè **sotto la soglia `< 50`**, e un'auto-dichiarazione muoverebbe un peso — esattamente ciò che questo brief toglie alla tecnica. Nessuna misura ⇒ nessun segnale.

⚠️ **Effetto collaterale obbligatorio da verificare: `endurance` si muove.** `_compute_endurance` è `0.8 × pe_score + tenure + eval + hang_duration`. Cambiando PE cambia endurance, meccanicamente. Sui dati reali:

| utente | PE ora → dopo | EN ora → dopo | nota |
|---|---|---|---|
| `7ea9f0ee` (autore) | 53 → **70** | 51 → **65** | il repeater smette di essere diluito 40/40 dal gap |
| `79fadc50` | 54 → **49** | 52 → **48** | **attraversa la soglia `< 50` su entrambi gli assi** |
| `22080848` | 67 → **86** | — | |
| gli altri 15 | invariati | invariati | nessun repeater → PE resta 50 |

Il caso `79fadc50` non è un bug: è il dato onesto che prima era mascherato. Ma va **inchiodato da un test**, perché è un cambio di piano reale prodotto da un brief che parla di tecnica.

### 2.3 `macrocycle_v1._adjust_domain_weights` — tecnica esce dalla mappa

Rimuovere `"technique": "technique"` da `axis_to_weight` (riga 439). Il peso base della fase (`.20` in base, `.25` in performance) resta intatto: **la tecnica non viene de-prioritizzata, smette solo di essere corretta da un'opinione.**

### 2.4 `macrocycle_v1._find_weakest_axis` — la trappola del 50 fantasma

Rimuovere `"technique"` dalla tupla di riga 297. **Non basta togliere l'asse dal profilo**: la funzione fa `profile.get(axis, 50)`, quindi un asse assente diventa un 50 fantasma — e verificato sui profili reali, quel fantasma **vince il titolo di asse più debole** per `79fadc50` e `f8ff8569`. Punteggia esattamente 50, quindi non fa scattare lo spostamento di durata (che richiede `< 50`), ma verrebbe riportato come debolezza al coach e a qualsiasi consumatore futuro.

Conseguenza sulle durate: sparisce lo spostamento `base +1 / performance −1` guidato dalla tecnica. Per gli atleti **lead** era già un no-op silenzioso (`_PHASE_FLOORS_LEAD["base"] == cap == 4`); per i **boulder** era reale, e un atleta con gap largo smette di perdere una settimana di Performance per una ragione proxy.

### 2.5 `profile_scoring_version` → `"profile_v2_gap_demoted"`

Mai retroattivo: i profili salvati conservano versione e numeri. La versione nuova vale dalla prossima valutazione o dalla prossima rigenerazione esplicita.

## 3. Il gap non viene cancellato — viene riclassificato

`_redpoint_onsight_gap` **resta** in `assessment_v1.py` anche senza chiamanti nello scoring: diventa la sorgente dello hint. Nessuna delle altre superfici che leggono i gradi RP/OS va toccata — usano i gradi **in assoluto**, non come differenza: `api/deps.py:603-614` (mirror in `performance.current_level`), `engine/outdoor_pitch_ladder.py` ([[A265]]), `engine/milestones_v1.py`, `routers/public_assessment.py:118` (il 422 su OS > RP).

### 3.1 Nel coach — estendere, non ricostruire

`coach/prompt_builder._profile_section` (riga 122) stampa già tutti e quattro i gradi ma non nomina il gap. **Una riga derivata, dentro il blocco che esiste già:**

```
- Onsight gap: 5 half-grades (lead RP 8a / OS 7a+). Tactics/style signal, NOT a technique
  measurement — the plan does not weight it. A wide gap in a redpoint-focused climber is a style
  choice; only call it a weakness if the athlete says they want to onsight.
```

Nessun payload nuovo, nessuna sezione nuova, nessun endpoint. **La frase di guardia non è decorativa:** senza, il modello legge un numero etichettato «gap» e diagnostica tecnica — lo stesso modo di fallimento che [[B305]] ha chiuso quando il coach ha imitato una stringa di formato e ha fabbricato una build.

`goal.target_style` (`api/models.py:54`, `Literal["redpoint", "onsight"]`) registra già l'intenzione che serve: gap largo + `onsight` è il caso da segnalare, gap largo + `redpoint` è il caso su cui tacere.

### 3.2 Nell'endpoint pubblico — un fix che serve subito

`public_assessment.py:164`: `weakest = min(_AXIS_PRIORITY, key=lambda axis: (profile[axis], _AXIS_PRIORITY.index(axis)))`.

`_AXIS_PRIORITY` mette la tecnica ultima **solo nei pareggi**, quindi può ancora vincere in assoluto. Con la tecnica ridotta a un'auto-dichiarazione, quel percorso direbbe a uno sconosciuto *«il tuo anello debole è la tecnica»* sulla base della tendina che ha appena compilato lui.

**Escludere `technique` dalla selezione dell'anello debole.** Resta nel radar e in `profile`; smette di poter essere la risposta. Se ne parla la copy della pagina, non il motore.

## 4. Copy da riscrivere — oggi diventa falsa

| file | testo attuale |
|---|---|
| `frontend/src/lib/gradeUtils.ts:249` (`AXIS_DESCRIPTIONS.technique.lead`) | «A big gap between your onsight and redpoint grades suggests there's free performance hiding…» — **nomina la misura che stiamo togliendo** |
| `frontend/src/app/onboarding/grades/page.tsx:133` | «…endurance and technique» |
| `frontend/src/app/assessment/page.tsx:359` | «The gap between this and your redpoint is what reveals technique and power endurance.» |

I gradi **restano una domanda obbligatoria**: alimentano la scaletta outdoor ([[A265]]), i milestone e lo hint del coach. È la promessa su cosa rivelano che cambia.

Nuova copy per l'asse tecnica: dire che è la **tua** lettura di te stesso, che informa il coach e non il piano. Sotto i 300 caratteri, verificato dal test che [[B304]] ha già scritto (`radar-tooltip.test.ts:146`).

⚠️ Il test `radar-tooltip.test.ts:129` asserisce che ogni riga `low` contenga il grado obiettivo. Se la nuova copy della tecnica smette di essere target-relative — e dovrebbe — quel test va aggiornato **consapevolmente**, non aggirato.

Aggiornare anche `docs/user_guide_v1.md` e `frontend/src/lib/guide-content.tsx` nello stesso commit ([[C268]] ha appena aggiunto la sezione «Reading the radar» a entrambe; la lezione di [[B320]] è che correggerne una sola lascia in piedi quella che l'utente legge davvero).

## 5. Test

### 5.1 Il test che avrebbe intercettato la distorsione originale

**Property test sui limiti di peso.** Per ogni combinazione `primary_weakness` × `secondary_weakness` × fase × disciplina, tenendo fissi gli assi misurati:

```
max |Δ peso_di_dominio| ≤ 0.02
```

Nessun singolo input soggettivo può muovere un peso di più di due punti percentuali. È l'asserzione che avrebbe fatto fallire i +7,5 pp il giorno in cui sono stati scritti.

### 5.2 Scoring

- Due profili identici tranne i gradi RP/OS producono **la stessa** tecnica.
- `profile_source.technique == "self_reported"` sempre.
- PE con repeater = `repeater_score + eval`, invariante al gap.
- PE senza repeater = **50 esatti**, `profile_source.power_endurance == "estimated"`.
- Payload di produzione dell'autore → PE **70**, EN **65** (fixture di regressione, il modo di [[B321]]).
- Payload di `79fadc50` → PE **49**, EN **48**: inchioda l'attraversamento della soglia, così non può più succedere di nascosto.
- Percorso boulder: un atleta con soli gradi Font continua a funzionare (`resolve_grade`, [[B321]]).

### 5.3 Pesi e durate

- `technique` non è in `_find_weakest_axis`: un profilo con tutti gli altri assi a 80 e nessuna chiave `technique` restituisce `(None, 101)`, **non** `("technique", 50)`.
- Pesi renormalizzati: somma `1.0 ± 1e-6`, ogni peso `≥ 0.02`, su tutti e 18 i profili di produzione.
- Durate di fase byte-identiche a oggi per ogni profilo **lead**; perdono esattamente lo spostamento guidato dalla tecnica per ogni profilo **boulder**.
- Peso `technique` dell'autore in base: `.275 → .202`. Il 7,3 pp torna distribuito su dita (.156→.172), tirata (.110→.121), PE (.138→.152) e volume (.229→.253).

### 5.4 Invarianti

- **Sessioni passate immutabili** (regola globale): ricalcolare il profilo, rigenerare, asserire che `session_completion_log`, `feedback_log`, `week_plans` passati e `working_loads` siano byte-identici.
- **Snapshot vs live** (regola globale): [[D271]] §6.2 ha verificato che `assessment_snapshot` e `profile_snapshot` sono scritti una volta e solo letti — un macrociclo attivo non viene mai ripesato sul posto. Riasserirlo con una fixture specifica sulla tecnica.
- **`is_macrocycle_stale` diventerà `True`** per gli utenti colpiti (la tecnica si muove di ≥ 5 punti). **È il comportamento corretto**: fa comparire il banner che lascia all'utente la scelta di rigenerare. Verificare che il percorso del banner preservi le sessioni completate — oggi lo fa, via `preserve_before`.

## 6. Cosa questo brief NON fa

- ❌ Non grigia la tecnica sul radar (§1: decisione grafica separata).
- ❌ Non introduce la regola generale «un asse `estimated` non partecipa ai pesi». Sarebbe la conclusione naturale, ma toccherebbe anche dita, tirata ed endurance e cambierebbe il piano di 8 utenti su 18 che non hanno test: merita il suo brief e la sua tabella controfattuale.
- ❌ Non tocca `_PE_REPEATER_BENCHMARK` (18→44 set), che [[D260]] §7 ha segnalato come **privo di fonte** e che dopo questo brief conta *di più*, perché il repeater smette di essere diluito. Registrato come debito, non risolto qui.
- ❌ Non implementa niente di [[D271]].

## 7. Se si vuole che l'auto-dichiarazione faccia ancora qualcosa

L'obiezione legittima a (c) è: «se un utente dichiara problemi di tecnica, il piano dovrebbe dargli tecnica». Lo strumento giusto **non è il peso di dominio** — è il pool condizionato di [[A258]], già usato per la tirata: si sblocca una sessione dedicata per chi dichiara quella debolezza, *in sostituzione e non in aggiunta*, invece di spalmare +10 pp su tutti i domini in tutte le fasi. Un input soggettivo può scegliere **una seduta**; non deve riscrivere il macrociclo.

Non incluso qui: è una regola in `_PROFILE_CONDITIONAL_SESSIONS` e va decisa con la sua sessione candidata (`technique_focus_gym` è già `primary` in base e performance, quindi servirebbe qualcosa di diverso, non un doppione).

## 8. Definizione di fatto

- [ ] [[A269]] mergiato e in produzione
- [ ] Property test sui limiti di peso verde (§5.1)
- [ ] Fixture di regressione per autore e `79fadc50`
- [ ] `technique` fuori da `_adjust_domain_weights` **e** dalla tupla di `_find_weakest_axis`
- [ ] Hint del gap nel coach, con la frase di guardia
- [ ] `technique` fuori dalla selezione dell'anello debole nell'endpoint pubblico
- [ ] Copy riscritta in tutti e tre i punti + entrambe le guide
- [ ] Invarianti §5.4 verificati, non assunti
- [ ] Suite backend + frontend verdi, `scripts/sync_status.py` eseguito
- [ ] `docs/ROADMAP_CURRENT.md`: [[D260-P1b]] chiuso nello stesso commit

---

*Brief pronto. Nessuna riga scritta. Serve OK di Daniele, e [[A269]] prima.*
