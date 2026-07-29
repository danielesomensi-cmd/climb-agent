# B308 — Frequenza garantita di stimolo di tirata (Fase 1: analisi)

> **Tipo:** B (bugfix) · **Origine:** [[D263]] punto 3, severità CRITICO dal KB · **Modulo:** `planner_v2.py` (⚠️ lista STOP di CLAUDE.md)
>
> ⛔ **FASE 1 — ANALISI. Nessuna riga scritta. Serve OK esplicito di Daniele prima della Fase 2.**

---

## 1. Il difetto

Un peso di dominio basso **non produce una dose bassa: produce assenza probabilistica.** Il peso influenza quali sessioni il planner preferisce, ma nulla garantisce che una qualità venga allenata con una certa frequenza. Per il mantenimento della forza massima la letteratura (Bickel 2011, Spiering 2021, Mujika & Padilla 2000) è netta: la variabile non negoziabile è **l'intensità**, e serve **frequenza garantita** — ~1 sessione/settimana anche a volume ridotto a 1/3.

Misurato sul macrociclo di Daniele: **6 settimane su 12** possono ospitare un blocco di tirata; `base`, `power_endurance` e `deload` ne sono prive. Oltre la finestra di grazia di ~4 settimane per la forza massima.

## 2. Il precedente che rende il fix a basso rischio

**Questo meccanismo esiste già.** `planner_v2.py:1213` — **PASS 2.5**:

```python
# ── PASS 2.5 (NEW-F9): Ensure PE phase has at least 1 finger maintenance session ──
if phase_id == "power_endurance":
    has_finger_maintenance = any(... for day_list in day_sessions for s in day_list)
    if not has_finger_maintenance:
        ...
```

È esattamente la stessa forma: *"in questa fase, se una certa qualità non è presente nel piano, forzala"*. Rispetta il gap dita, preferisce un giorno vuoto e in alternativa **sostituisce** una sessione complementare (mai una primaria). Il fix proposto è una **seconda istanza di un pattern già in produzione e già testato**, non un meccanismo nuovo.

## 3. Cosa cambierebbe

Nuovo **PASS 2.6** dopo il 2.5, con questa logica:

- **Quando:** `phase_id not in ("deload",)` — il KB conferma che zero in deload è difendibile.
- **Condizione:** nessuna sessione del piano contiene un blocco che serva l'asse `pulling_strength`.
- **Azione:** collocare una sessione che lo copra, con le stesse regole del 2.5 — giorno vuoto per primo, altrimenti sostituzione di una **complementare**, mai di una primaria; rispetto del gap dita e del gap giorni duri; nessuno sforamento di `effective_hard_cap`.
- **Se non c'è spazio:** non forzare. Registrare il fallimento nel plan (come `skipped_tests` fa per i test) invece di sacrificare un vincolo di sicurezza.

**Nota sulla cadenza 7-10 giorni:** il planner genera **una settimana per volta** e non ha memoria strutturale delle settimane precedenti se non via `prev_week_plan`. Una regola "ogni 7-10 giorni" richiederebbe di leggere lo storico; una regola "≥1 a settimana" è implementabile con ciò che esiste ed è **più conservativa** (più frequente, non meno). **Proposta: settimanale.** Se Daniele preferisce la cadenza 7-10 giorni, il costo è leggere `prev_week_plan` — fattibile ma è un secondo pezzo di stato da gestire.

## 4. Superficie d'impatto (call site e consumatori)

`generate_phase_week` è chiamata da:

| chiamante | contesto |
|---|---|
| `api/routers/week.py:440` | generazione settimana (produzione) |
| `engine/start_date_utils.py:75` | shift dello start_date |
| `engine/replanner_v1.py` (via `_build_session_pool`) | rigenerazione dopo replan |

Consumatori del piano prodotto: `/api/week/{n}`, il replanner, i report settimanali, la UI `/week` e `/today`.

**Test che toccano `generate_phase_week`:** ~20 file, fra cui `test_planner_v2.py`, `test_b297_test_placement.py`, `test_youth_cap.py`, `test_b165b_recovery_multiplier.py`, `test_b94_equipment_mismatch.py`, `test_weekly_override.py`, `test_availability_edit.py`, `test_quick_add.py`, `test_replanning_v1.py`, `test_d154_sp_climbing_fix.py`, `test_b157_pe_equipment_gate.py`.

**Rischio principale:** molti di questi test asseriscono la **composizione esatta** della settimana. Aggiungere una sessione garantita cambierà il conteggio in alcuni. Come già visto in A257 e C260-bis, la regola è: verificare caso per caso se il test asseriva l'invariante che dichiara o un dettaglio di selezione, e **rafforzarlo**, non piegarlo.

## 5. Invarianti da preservare (verifica obbligatoria in Fase 3)

- **Sessioni passate immutabili** (CLAUDE.md, non negoziabile): PASS 2.6 opera sulla settimana in generazione, mai su settimane passate. Da testare esplicitamente con una rigenerazione su settimana con giorni `done`.
- **Tetto giorni duri** e **gap dita 48h**: la nuova sessione non deve mai violarli. Se lo farebbe, non si colloca.
- **Determinismo**: stesso input → stessa settimana.
- **`from_phase="current"`** nelle chiamate a `generate_macrocycle`: non toccato da questo brief, ma da riverificare perché siamo in area planner.
- **Deload intatto**: nessuna sessione di tirata iniettata in deload.

## 6. Decisioni

**1. Cadenza — DECISO: settimanale.** ✅ OK di Daniele 2026-07-29 ("sui 7 giorni ok, se è semplice"). È l'opzione semplice: il planner genera una settimana per volta e il controllo "questa qualità è presente nel piano?" si fa sui dati già in mano, senza leggere lo storico. Più conservativa della finestra 7-10 giorni, mai meno frequente.

**2. Fallimento silenzioso o visibile — RACCOMANDO: visibile.** Registrarlo nel piano sul modello di `skipped_tests`, che già esiste per lo stesso motivo. La ragione non è cosmetica: [[D263]] è rimasto invisibile per mesi proprio perché l'assenza di uno stimolo non produce alcun segnale. Uno stimolo dichiarato "garantito" che silenziosamente non viene erogato ricrea esattamente la classe di bug che questo brief chiude. Costo: un campo nel plan + una riga di UI (opzionale, si può anche solo loggare in prima battuta).

**3. Quale sessione collocare** quando manca la tirata: dipende dall'azione 2 del KB (blocco di tirata in `base`/`power_endurance`) — vedi §7. Se [[A258]] è già in produzione e l'utente ha la tirata debole, `pulling_strength_gym` è il candidato naturale; per tutti gli altri serve il blocco nelle sessioni esistenti.

## 7. Ordine consigliato

Questo brief **dipende** dall'azione 2 del KB (aggiungere un blocco di tirata a `base` e `power_endurance`): senza una sessione che copra la tirata in quelle fasi, PASS 2.6 non avrebbe nulla da collocare. Ordine: **azione 2 (catalogo, effort S) → B308 → [[A258]]**.

---

⛔ **STOP — Fase 1 completa. In attesa di OK esplicito prima di scrivere codice.**
