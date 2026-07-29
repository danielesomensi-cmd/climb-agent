# D261 — Perché il composer adhoc non produce i bloccaggi (audit read-only)

**Data:** 2026-07-29 · **Tipo:** D (audit, nessuna modifica applicata) · **Origine:** residuo aperto da [[B305]]/[[C260]], sintomo riportato da Daniele nella conversazione coach del 2026-07-28.

**Stato:** ⛔ **Fase 1 completa — in attesa di OK esplicito.** L'area tocca `resolve_session.py` (lista STOP di CLAUDE.md), il catalogo esercizi e due sessioni + un template del planner. Nessuna riga è stata modificata da questo brief.

---

## 1. Il sintomo e l'ipotesi sbagliata

Daniele chiede *"core e bloccaggi monobraccio"*; il composer produce trazioni assistite e row, senza il bloccaggio isometrico. L'ipotesi che avevo formulato il 28/07 — e che questo audit **smentisce come causa primaria** — era:

> il pattern `pull_vertical` è sovraffollato (12 esercizi su 14 della famiglia pulling lo condividono) e il cap `MAX_PER_PATTERN = 2` esclude il lock-off.

Il sovraffollamento è reale, ma **non è ciò che tiene fuori il bloccaggio**. La causa vera è un'altra, più grave e molto più estesa.

## 2. Causa reale: la selezione è alfabetica

`adhoc_builder._rank_key` (righe 128-137) ordina i candidati con tre criteri:

```python
return (
    not _phase_match(ex, phase),        # 1) affinità di fase
    str(ex.get("id") or "") in recent,  # 2) non visto di recente
    str(ex.get("id") or ""),            # 3) tie-break stabile sull'id
)
```

Misurato sul catalogo attuale:

| Termine | Valore reale | Conseguenza |
|---|---|---|
| 1) `phase_affinity` | presente su **1 esercizio su 255** (`fall_practice`) | sempre `True` → non discrimina mai |
| 2) `id in recent` | i candidati sono già filtrati con `exclude=used`, e `used` parte da `set(recent)` | sempre `False` → **termine morto** |
| 3) `id` | — | **decide da solo** |

Quindi l'ordinamento collassa sull'**ordine alfabetico dell'id**. Non è una degradazione occasionale: è il comportamento in ogni sessione adhoc composta finora. Le prove nelle sessioni generate ieri sono inequivocabili:

- pulling: `archer_pullup` → `band_assisted_pullup` → `barbell_row` (a, b, b)
- core: `ab_wheel_rollout` → `back_extension` → `cable_woodchop` → `copenhagen_plank` → `dead_bug` (a, b, c, c, d)

`lock_off_isometric` perde perché comincia per **L**. Non perché sia meno adatto.

Copertura di `phase_affinity` per bucket di focus (`0/N` = ranking puramente alfabetico):

| focus | con affinità / candidati |
|---|---|
| fingers | 0 / 38 |
| pull | 0 / 33 |
| power | 0 / 16 |
| endurance | 0 / 21 |
| core | 0 / 28 |
| general_strength | 0 / 65 |
| technique | 1 / 43 |
| mobility | 0 / 27 |
| prehab | 0 / 19 |

**Nota di allineamento docs↔codice:** la entry di roadmap di [[A243]] descrive il builder come *"equipment- e phase-aware via `phase_affinity`"*. Il codice legge davvero quel campo, ma il campo non esiste nei dati: la parte **phase-aware è di fatto inattiva**. `phase_affinity` è consumato **solo** da `adhoc_builder.py:122` — il planner (`resolve_session`, `planner_v2`) non lo usa, quindi il problema è confinato al composer adhoc.

## 3. Causa secondaria: `pattern` è l'asse di diversità sbagliato

`MAX_PER_PATTERN = 2` serve a evitare "cinque varianti della stessa trazione". L'asse scelto è `pattern`, che però è troppo grosso: 12 dei 14 esercizi pulling sono `pull_vertical`, quindi il cap taglia esercizi genuinamente diversi (un bloccaggio isometrico *non* è una trazione).

Il catalogo ha già l'asse giusto: **`recency_group`**, che è il concetto di "stessa famiglia" usato da B159b per la penalità di recenza.

| esercizio | `pattern` | `recency_group` |
|---|---|---|
| pullup, archer, typewriter, l_sit, weighted, power, band_assisted | pull_vertical | `pullup_variants` |
| **lock_off_isometric** | pull_vertical | **`pullup_lock_off`** |
| **one_arm_pullup_assisted** | pull_vertical | **`pullup_one_arm`** |
| eccentric_pullup | pull_vertical | `pulling_vertical` |
| frenchies, uneven_grip_pullup | pull_vertical | `vertical_pull` |
| weighted_chinup | [pull_vertical, elbow_flexion] | `biceps_pull_compound` |

`recency_group` distingue già lock-off e monobraccio dalle trazioni generiche, dove `pattern` non lo fa.

⚠️ **Igiene:** `vertical_pull`, `pulling_vertical` e `pullup_variants` sono tre etichette diverse per famiglie quasi sovrapposte. Da normalizzare **prima** di usare questo campo come asse decisionale, altrimenti si sposta il problema invece di risolverlo.

## 4. Perché lo split di `pull_vertical` è la soluzione sbagliata

L'idea di dare a `lock_off_isometric` un pattern dedicato (`pull_isometric`) **romperebbe il planner**. `pulling_strength_compound.json` ha tre blocchi che filtrano tutti `pattern: ["pull_vertical"]`, e il secondo si chiama letteralmente `lock_off_hold`:

```
weighted_pullup_main  → role=main, domain=strength_general, pattern=pull_vertical
lock_off_hold         → role=main, domain=strength_general, pattern=pull_vertical   ← si aspetta il lock-off
typewriter_unilateral → role=main, domain=strength_general, pattern=pull_vertical
```

Togliendo `lock_off_isometric` da `pull_vertical`, quel blocco non potrebbe **mai più** selezionare un bloccaggio: cadrebbe su un'ennesima variante di trazione (i 3 blocchi si differenziano solo per il dedup su `exclude_ids`, `resolve_session.py:585`), e il design "pesante → bloccaggio → unilaterale" collasserebbe in tre trazioni. Sarebbe una regressione del piano peggiore del sintomo adhoc che vogliamo curare.

**Consumatori di `pull_vertical` da preservare** (verificati, `_archive` escluso):

| file | blocco | filtro |
|---|---|---|
| `templates/v1/pulling_strength_compound.json` | `weighted_pullup_main`, `lock_off_hold`, `typewriter_unilateral` | role=main, domain=strength_general, pattern=pull_vertical |
| `sessions/v1/strength_long.json` | `pulling_compound` (secondary, `required:false`) | idem |
| `sessions/v1/limit_boulder_gym.json` | `supplementary_pulling` (secondary, `required:false`, `pick:1`) | idem |

Baseline misurato: il filtro isolato produce **10 candidati** e seleziona `archer_pullup`; in `limit_boulder_gym` risolto end-to-end il blocco `supplementary_pulling` seleziona `archer_pullup`. Questo è il riferimento contro cui verificare qualunque modifica.

## 5. Opzioni

### Opzione 1 — Popolare `phase_affinity` (risolve la causa primaria)
Assegnare l'affinità di fase agli esercizi, almeno sui bucket principali. È l'unico intervento che rende la selezione *motivata* invece che alfabetica, ed è quello che [[A243]] già dichiara di fare.
- **Raggio:** solo `adhoc_builder` (unico consumer). Zero impatto su planner e piani esistenti.
- **Costo:** è lavoro di dominio, non di codice — richiede una decisione metodologica per ~255 esercizi (o un sottoinsieme prioritario). Va fatto con la KB, non a intuito.
- **Rischio:** basso tecnicamente, alto in termini di *tempo tuo*.

### Opzione 2 — Spostare il cap di diversità da `pattern` a `recency_group`
Una riga in `_pattern_of`, previa normalizzazione delle tre etichette duplicate.
- **Raggio:** solo `adhoc_builder`. **Zero** modifiche al catalogo e ai template → il planner non si accorge di nulla.
- **Effetto misurato** (simulato su stato prod, focus=pull+core, casa di Daniele, 60 min):
  - oggi: `archer_pullup, band_assisted_pullup, barbell_row, inverted_row`
  - con `recency_group`: `archer_pullup, eccentric_pullup, band_assisted_pullup, barbell_row`
  - → **più varietà reale, ma da sola NON basta**: il bloccaggio resta fuori perché il problema è il ranking alfabetico (Opzione 1), non il cap.
- **Rischio:** basso.

### Opzione 3 — Granularità dell'intent: `focus=lock_off`
Aggiungere un focus dedicato che mappi su `lock_off_endurance`, così "bloccaggi" smette di essere annegato nel bucket `pull`.
- **Raggio:** `FOCUS_DOMAINS` + enum del tool di estrazione + prompt. Solo composer.
- **Nota:** i domini `lock_off_endurance` esistono già sui 4 esercizi giusti (aggiunti da B305).
- **Rischio:** basso. È il fix più diretto per **questo** sintomo specifico.

### Opzione 4 — Split di `pull_vertical`
❌ **Sconsigliata**, vedi §4. Rompe `lock_off_hold` nel template del planner.

## 6. Raccomandazione

Nell'ordine: **Opzione 3** (chiude il sintomo riportato, mezz'ora, rischio minimo) → **Opzione 2** (igiene `recency_group` + cap, migliora ogni sessione) → **Opzione 1** come brief separato e pianificato, perché è l'unica che sana la causa radice ma è lavoro di dominio, non di codice.

**Non fare l'Opzione 4.**

## 7. Esito

**OK di Daniele il 2026-07-29 su Opzione 3 + Opzione 2** → implementate in [[B307]] (backend-only). Opzione 1 (popolare `phase_affinity`) **resta aperta** come brief di dominio: finché non è fatta, il tie-break dentro ogni bucket rimane alfabetico — i focus più stretti introdotti qui mascherano il sintomo, non lo curano.

Verifica end-to-end con estrazione LLM reale e stato prod, sul messaggio originale del 28/07:

| richiesta | prima | dopo |
|---|---|---|
| "core e bloccaggi monobraccio, 60 min, casa" | trazioni assistite + row, **zero bloccaggi** | core + Archer + **Frenchies** + **Lock-off Isometric** |
| "45 min di soli bloccaggi" | non esprimibile (annegava in `pull`) | Archer, Lock-off Isometric, One-Arm, Typewriter, Frenchies, Uneven-Grip |
| "sessione di trazioni" (controllo non-regressione) | archer, band-assisted, barbell row, inverted row | idem + lock-off e frenchies, 4 famiglie invece di 2 |

Opzione 4 (split di `pull_vertical`) **non** eseguita, come raccomandato: i tre blocchi di `pulling_strength_compound` continuano a filtrare `pull_vertical` e il baseline del §4 è invariato.

## 8. Cosa NON è stato toccato dall'audit

L'audit in sé (§1-§6) non ha modificato nulla: `git status` pulito all'apertura e alla chiusura. Le misure sono riproducibili con lo stato prod di Daniele e il catalogo a 255 esercizi (commit `9f8529c`). Le modifiche descritte al §7 sono di [[B307]], commit successivo.
