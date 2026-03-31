# Lessons Learned

Patterns, mistakes, and non-obvious behaviors discovered during development.
Claude Code appends entries here after sessions where something unexpected happened.
Periodically reviewed and promoted to CLAUDE.md if they represent universal rules.

## Format
- **[YYYY-MM-DD] [BRIEF-ID or context]**: One-line lesson.

## Lessons

<!-- Entries below this line -->
- **[2026-03-31] [B169]**: `user_state.equipment.gyms` usa `gym_id` UUID (assegnato da `_ensure_gym_ids` in onboarding), ma il frontend caricava i gym con cast `{ name, equipment }` perdendo il campo — il dialog passava il nome come gym_id, il resolver non trovava match e usava il fallback (primo gym per priorità). Quando si propagano identificatori tra frontend e backend, verificare sempre che il campo chiave usato dal resolver (`gym_id`) sia incluso nel tipo TypeScript e nel cast dello state.
