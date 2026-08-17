# D277 — Audit di allineamento documentazione ↔ codice

**Tipo:** D (audit, read-only sul codice) · **Data:** 2026-08-17 · **Precedente:** [D269](D269_roadmap_docs_audit.md) (2026-08-02, 35 brief fa)

Innescato dal warning di `repo_hygiene.py` («35 brief dall'ultimo audit»). Copre ciò che
quel controllo automatico **non** sa vedere: se quello che i documenti dichiarano è ancora
vero. Nessuna riga di logica applicativa è stata toccata; le uniche modifiche sono a
documenti, a `scripts/repo_hygiene.py` (data dell'ultimo audit) e alla collocazione di
nove file.

---

## Il risultato in breve

**La documentazione regge meglio di quanto il warning suggerisse.** Le due cose che si
sbagliano più spesso — la tabella degli endpoint e i contatori — sono **esatte al 100%**,
e nei documenti vivi non c'è un solo riferimento a file rotto che non fosse già annotato
come tale. I sei finding sono di completezza e collocazione, non di correttezza sostanziale.

### Verificato corretto (nessuna azione)

| Cosa | Verifica | Esito |
|---|---|---|
| Tabella endpoint `CLAUDE.md` | 93 righe estratte dalla tabella vs 93 rotte reali (91 router + `/health` + il webhook Stripe, registrato via `add_api_route` in `main.py:166` e quindi invisibile a un grep sui decoratori) | **Zero deriva in entrambe le direzioni** |
| Numero di router | 26 `include_router` in `main.py`; 27 file in `routers/` di cui uno è `__init__.py` | ✅ |
| Contatori | tests 3242, esercizi 263, sessioni 35, template 19, pagine 46, componenti 110 | ✅ tutti esatti |
| `ENGINE_ARCHITECTURE.md` | i 5 moduli citati esistono tutti | ✅ |
| Variabili d'ambiente in tabella | ognuna è realmente letta dal backend | ✅ nessuna riga fantasma |
| `docs/audits/` (plurale, vietata da `CLAUDE.md`) | assente | ✅ |
| `user_guide_v1.md` | copre pitch ladder (§14 «Plan for the day»), boulder-only, session builder, body-part, mobility, coach, scala Elite | ✅ — la ricerca per parola chiave dà falsi negativi perché la guida usa il linguaggio dell'utente, non quello del codice |
| Numerazione brief | nessuna collisione; `next_brief.py` scansiona git oltre alla roadmap | ✅ |

---

## Finding

### F1 — Il conteggio delle pagine in `CLAUDE.md` non tornava (P2, corretto)

`CLAUDE.md` dichiarava «**Pages (46):** … + 15 under `/onboarding` (index + 14 route dirs) + …».
Il totale 46 è giusto, ma **la somma degli addendi faceva 45**, e il sotto-conteggio era
sbagliato: sul disco ci sono **15 route dir** sotto `/onboarding` più l'index, cioè **16**.

Ricostruita la genesi con `git log -S`: prima di [B320] il testo diceva «16 under
`/onboarding` (index + 15 route dirs)» con totale 47 — ma allora le route dir erano 16
(c'era ancora `recover`), quindi **il testo era già corto di uno**. B320 ha cancellato
`recover` e ha decrementato il sotto-conteggio *sopra* un numero già sbagliato: il totale
è finito giusto per il motivo sbagliato, e l'errore è sopravvissuto a D269.

La stessa cifra compariva una seconda volta nella sezione onboarding («14 route dirs»),
anche lì sbagliata. **Entrambe corrette.** La lezione operativa è nel testo nuovo:
*verificare la somma, non solo il totale in testa* — un totale che quadra per caso non
segnala nulla.

### F2 — Quattro variabili d'ambiente lette in produzione e non documentate (P2, corretto)

`CLAUDE.md` ha una tabella delle env var di Railway. Confrontata con ogni
`os.environ.get` / `os.getenv` del backend (test esclusi):

| Variabile | Default | Perché conta |
|---|---|---|
| `COACH_MAX_TOKENS` | `2048` | **È la manopola del finding aperto `COACH-TRUNCATION-RESIDUAL`.** `llm_client.py:81` logga letteralmente «raise COACH_MAX_TOKENS or tighten L1» quando una risposta è tagliata: il rimedio esisteva nel codice mentre la variabile non compariva in nessun documento. |
| `RATE_LIMIT_ENABLED` | on (`!= "0"`) | Spegne **tutto** il rate limiting. Il default è sicuro, ma è un interruttore di sicurezza e non era scritto da nessuna parte. |
| `TRACE_RESOLVE` | `false` | Trace verboso del resolver (B126), pensato per il debug su Railway. |
| `WEEKPLAN_ARCHIVE_LAZY` | `false` | Commuta l'archiviazione dei week plan di A221 da eager a lazy. |

Nessuna variabile documentata risulta non letta: la tabella era incompleta, non falsa.

### F3 — Tre audit non trovabili per ID (P3, corretto)

`CLAUDE.md` prescrive: «All audit deliverables live in `docs/audit/<brief-id>_<topic>.md`».
Tre deliverable stavano nella radice di `docs/`, e **due non erano rintracciabili per ID
perché il nome non lo conteneva affatto**:

- `docs/audit_plan_pause.md` → in realtà **D246** → `docs/audit/D246_plan_pause.md`
- `docs/audit_outdoor_handling.md` → in realtà **D247** → `docs/audit/D247_outdoor_handling.md`
- `docs/audit_D260_tooltip_and_assessment_scoring.md` → `docs/audit/D260_tooltip_and_assessment_scoring.md`

Spostate lì anche le due analisi D-type che stavano in radice (`analysis_D271_*`,
`analysis_D272_*`): sono deliverable di brief D come gli altri. Tutti i riferimenti sono
stati riscritti e verificati.

### F4 — Brief chiusi nella radice di `docs/` mentre esiste `docs/briefs/` (P3, corretto)

`A224_weather_integration.md`, `A245_review_remediation_v1.md` e `megabrief_final_report.md`
(il report finale dell'overhaul assessment, cioè A267) stavano in radice; i brief recenti
— A269, A270, A271 — vivono invece in `docs/briefs/`. Spostati, con `megabrief_final_report.md`
rinominato `A267_megabrief_final_report.md` perché il nome non diceva a quale brief
appartenesse.

Archiviato in `_archive/docs/` anche `adhoc_coach_v1_track.md`, che si dichiara
«DRAFT brief, ready to execute after v0 (A237) field validation»: A237 è chiuso da mesi e
il lavoro è stato consegnato da A243 e A259. Era una bozza che descriveva un futuro già
passato.

### F5 — Il check dei brief chiusi guarda solo le prime 10 righe (P3, non corretto)

`repo_hygiene.check_completed_briefs()` cerca i marcatori di completamento **nelle prime
10 righe** di ogni `.md` in `docs/`. A224 e A245 non li hanno, quindi il check stampava
`[OK] No completed brief docs found in docs/` mentre due brief chiusi erano lì da mesi —
ed è il motivo per cui F4 è rimasto invisibile a ogni run.

**Non corretto di proposito:** allargare l'euristica (per esempio «un file che si chiama
`<ID>_*.md` in radice è fuori posto») è una modifica di comportamento dello strumento di
igiene, e va decisa, non infilata dentro un audit. Registrato qui perché la prossima
persona che legge un `[OK]` da quel check sappia quanto vale.

### F6 — 19 brief nei commit e in nessuna roadmap (P3, informativo)

Riconciliando i 340 ID di brief presenti nei subject dei commit con entrambe le roadmap,
19 non compaiono da nessuna parte: `A120`, `A222`, `B103`, `B104`, `B112`, `B113`, `B118`,
`B119`, `B122`, `B211`, `C130`, `C132`, `C206`, `C238`, `C252`, `C253`, `C254`, `D130`,
`D160`. Controllati uno per uno: sono **tutti** di manutenzione — sync di contatori,
archiviazione documenti, ritocchi di catalogo, remediation D236 — cioè brief che non
chiudevano alcun item di roadmap e quindi non avevano una riga da spuntare.

**Nessuna azione.** La numerazione è al sicuro perché `next_brief.py` scansiona `git log --all`
oltre alla roadmap, che è esattamente la ragione per cui quella regola esiste. Registrato
perché il prossimo audit non debba riderivarlo per poi concludere lo stesso.

---

## Riferimenti a file rotti — la misura, con la sua interpretazione

Scansione di ogni percorso fra backtick in tutti i `.md` del repo: **364 riferimenti
rotti**. Il numero da solo è allarmante e fuorviante, quindi va letto diviso:

| Dove | Quanti | Che cosa significa |
|---|---|---|
| Report di audit storici (`docs/audit/**`, `docs/research_kb/**`) | **267** | **Atteso, non un difetto.** Sono documenti *point-in-time*: D164 cita `backend/engine/adaptation/closed_loop.py` perché nel marzo 2026 esisteva, e B299 lo ha cancellato. Riscriverli falsificherebbe un referto. |
| `ROADMAP_v2.md` (archivio congelato) | 24 | Idem: `CLAUDE.md` lo dichiara «frozen, do not update». |
| Documenti **vivi** | **5 → 3** | Gli unici che contavano. |

Dei 5 nei documenti vivi ne restano **3**, tutti relativi a file **cancellati** e ora
annotati esplicitamente come tali («vive solo nella storia git»): `frontend_audit_D163.md`
(già documentato così nella roadmap), `claude_code_mega_brief_v1.md`,
`training_methodology_explained.md`. Corretti invece i due che puntavano a file
**esistenti ma altrove**: `horst_integration_audit.md` (4 occorrenze in `ROADMAP_BACKLOG`,
sta in `docs/research_kb/`) e `A214_phase0_audit.md` (in `_archive/docs/audit/`).

**`CLAUDE.md`, `PROJECT_BRIEF.md`, `README.md`, `user_guide_v1.md`, `ENGINE_ARCHITECTURE.md`
e `vocabulary_v1.md` non hanno alcun riferimento rotto.**

---

## Cosa questo audit NON copre

Una **code review** completa. L'ultima resta [D254](D254_full_repo_review.md) (2026-07-20),
e il commento in cima a `repo_hygiene.py` lo dice già. Questo audit verifica che i
documenti descrivano il codice; non giudica il codice.
