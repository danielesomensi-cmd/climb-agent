Aggiorna la documentazione di progetto dopo una sessione di lavoro.

1. **`docs/ROADMAP_v2.md`**: aggiorna gli stati dei B-items modificati durante la sessione (🔲→✅ o 🔲→🔧). Aggiorna l'header con data odierna e contatori (test, sessioni, esercizi, templates).

2. **`PROJECT_BRIEF.md`**: aggiorna la tabella delle fasi e i contatori (test count, sessioni, esercizi, templates).

3. **`CLAUDE.md`**: aggiorna il test count nel commento del comando pytest e in qualsiasi altro punto dove appare il numero di test.

**Non toccare** sezioni di design, architettura, o spiegazioni tecniche. Solo contatori e stati.

Poi committa:

```bash
git add docs/ROADMAP_v2.md PROJECT_BRIEF.md CLAUDE.md && git commit -m "docs: sync post-session"
```
