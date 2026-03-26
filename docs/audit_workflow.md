# Literature Audit Workflow

> Repeatable 3-step process for auditing climb-agent's training engine against climbing science literature.
> Last used: 2026-03-26 (D161)

---

## Step 1 — Extract snapshot (Claude Code)

```bash
cd ~/Projects/climb-agent
python scripts/extract_audit_snapshot.py \
  --user-id 7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e \
  --output docs/audit_snapshot_$(date +%Y-%m-%d).md
```

The script fetches the user's live state from the production API (falls back to local data if offline). Output: 12 sections + appendix covering macrocycle, planner, sessions, templates, exercises, resolver, progression, safety, user plan, cues, load model, and known gaps.

**Verify:** check that Section 9 shows "Source: Production API" and contains real week plans with resolved sessions.

---

## Step 2 — Literature audit (Knowledge Climbing project)

1. Open the **"knowledge climbing"** project on claude.ai
2. Paste the **audit prompt template** (below) as the FIRST message
3. Then paste the snapshot content (from the generated markdown file)
4. If the snapshot is too long (>100k chars), split into 2-3 messages:
   - Message 1: Sections 1-6 (engine structure)
   - Message 2: Sections 7-12 + Appendix (progression, safety, user, gaps)

The Knowledge Climbing project has access to: Horst, Lattice, Eva Lopez, Tyler Nelson/C4HP, StrengthClimbing, Michailov, Giles, Consuegra, Anderson, Matros, and other climbing training literature.

---

## Step 3 — Implementation brief (climb-agent project)

1. Copy the audit report from the Knowledge Climbing project
2. In the climb-agent project (Claude Code or claude.ai), triage findings by severity:
   - **Red** — critical issues (wrong/dangerous training logic)
   - **Yellow** — significant improvements
   - **Green** — nice-to-have optimizations
3. Cross-reference with `docs/ROADMAP_CURRENT.md` — many findings may already be tracked as deferred decisions
4. Generate implementation briefs for red/yellow items
5. Update roadmap with any new findings not already tracked

---

## Suggested frequency

- Every ~month or after significant engine changes (planner, resolver, macrocycle, progression)
- After adding new exercise categories or session types
- Before major releases

---

## Audit prompt template

Copy everything between the START/END markers below into the Knowledge Climbing project as the first message, followed by the snapshot content.

---START PROMPT TEMPLATE---

Sei un esperto di scienza dell'allenamento per l'arrampicata. Hai accesso a tutta la letteratura nel knowledge base di questo progetto (Horst, Lattice, Eva Lopez, Tyler Nelson/C4HP, StrengthClimbing, Michailov, Giles, Consuegra, Anderson, Matros, e tutti gli altri).

Ti passo lo snapshot completo del motore di pianificazione di climb-agent — un'app deterministica che genera piani di allenamento personalizzati per scalatori. Devi fare un audit full confrontando l'implementazione con la letteratura scientifica.

L'utente di riferimento e Daniele Somensi, lead climber, obiettivo 8a->8a+ (Fontainebleau), boulder 7C, 76kg, 182cm, intermedio/avanzato.

Produci un report con 8 sezioni. Per ogni finding indica:

- Severita: rosso CRITICO (piano sbagliato/pericoloso), giallo IMPORTANTE (migliorerebbe significativamente), verde NICE (ottimizzazione)
- Riferimento letteratura: quale fonte/studio/autore
- Azione suggerita: cosa fare (e se e gia in roadmap, segnalalo)

AUDIT 1: PERIODIZZAZIONE — durate fasi, pesi dominio per fase, DUP, deload, progressione tra fasi. Per Daniele: il macrociclo attuale e appropriato per 8a+?

AUDIT 2: SESSIONI — completezza catalogo (34 sessioni), tutti i tipi necessari?, assignment alle fasi corrette?, mix per lead climber intermedio/avanzato?

AUDIT 3: CARICO E DISTRIBUZIONE — sessioni/settimana, distribuzione hard/easy/rest, sovrapposizione stress (es. hangboard giorno prima di limit bouldering), recovery, volume totale. Usa il piano di Daniele come esempio concreto.

AUDIT 4: TEMPLATE — ordine blocchi intra-sessione, esercizi per blocco, durata stimata, blocchi mancanti (warmup? cooldown? prehab?)

AUDIT 5: ESERCIZI GAP ANALYSIS — per categoria, abbastanza esercizi? Mancano esercizi chiave? Parametri corretti (sets/reps/rest/intensity)? Domain e intensity_level corretti? Phase_affinity corrette?

AUDIT 6: RESOLVER — pipeline P0 corretto? Varieta sufficiente? Safety gates sufficienti? Ordine esercizi intra-sessione? Per Daniele: gli esercizi selezionati hanno senso per la sua fase?

AUDIT 7: PROGRESSIONE — feedback 5-livelli sufficiente? Moltiplicatori nel range giusto? Sovraccarico progressivo? Gap critici? (deload auto, plateau detection, autoregolazione)

AUDIT 8: GAP COMPLESSIVI — top 5 critici, top 5 gia in roadmap, cose non in roadmap che dovrebbero esserci, raccomandazioni per prossimo ciclo, per Daniele: il piano e buono? Cosa cambieresti?

Ogni finding deve essere actionable. Se e gia in roadmap (lista nella Section 12 dello snapshot), segnalalo esplicitamente. Se qualcosa non e chiaro, dillo piuttosto che assumere. Il report sara usato per generare un mega brief v2.

---END PROMPT TEMPLATE---
