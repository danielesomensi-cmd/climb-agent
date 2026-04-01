# Lessons Learned

Patterns, mistakes, and non-obvious behaviors discovered during development.
Claude Code appends entries here after sessions where something unexpected happened.
Periodically reviewed and promoted to CLAUDE.md if they represent universal rules.

## Format
- **[YYYY-MM-DD] [BRIEF-ID or context]**: One-line lesson.

## Lessons

<!-- Entries below this line -->
- **[2026-03-31] [B169]**: `user_state.equipment.gyms` usa `gym_id` UUID (assegnato da `_ensure_gym_ids` in onboarding), ma il frontend caricava i gym con cast `{ name, equipment }` perdendo il campo — il dialog passava il nome come gym_id, il resolver non trovava match e usava il fallback (primo gym per priorità). Quando si propagano identificatori tra frontend e backend, verificare sempre che il campo chiave usato dal resolver (`gym_id`) sia incluso nel tipo TypeScript e nel cast dello state.
- **[2026-03-31] [debug produzione]**: Per leggere lo stato di un utente in produzione NON usare `X-Clerk-User-Id` — il backend non accetta quell'header per `/api/state`. Il flusso corretto è: (1) `GET /api/admin/users` con `X-Admin-Key` per listare tutti gli UUID interni con nome/grade, (2) identificare l'UUID corretto, (3) `GET /api/state` con header `X-User-Id: <uuid>` + `X-Admin-Key`. Senza `X-Admin-Key` il backend usa solo Clerk JWT e non è invocabile da curl.
- **[2026-03-31] [B178]**: Gli script diagnostici non devono mai hardcodare path di file catalog/data. Includere sempre uno step di discovery (`find`) prima di qualsiasi script path-dependent. Path hardcodati hanno causato falsi risultati MISSING nell'audit del campo `unilateral`. Si applica a tutte le fasi D-type e B-type.
- **[2026-03-31] [B179]**: Negli script diagnostici su user_state, verificare sempre il key path esatto dalla struttura reale (es. `state["working_loads"]`, NON `state["baselines"]["working_loads"]`). Path annidati sbagliati restituiscono silenziosamente valori vuoti/mancanti e causano falsi allarmi P1. Aggiungere `print(list(state.keys()))` in cima a ogni diagnostica per confermare la struttura prima di scendere nei campi.
- **[2026-03-31] [B174]**: Bug items fixati in un brief ma non marcati Done in ROADMAP_CURRENT.md causano tempo perso a re-investigare lavoro già chiuso. Regola: ogni brief che chiude un item del roadmap DEVE includere uno step che lo marca Done prima della fine della sessione.
- **[2026-04-01] [B182]**: Audit remediation briefs (B165a-e) marked their own rows ✅ Done but left 16 individual P1 findings unmarked in the roadmap. The `/brief` command then reported these ghost findings as open, causing repeated confusion. Rule added: when closing findings via remediation brief, remove each finding from the P1 list — the P1 list IS the source of truth for open items.
