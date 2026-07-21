/**
 * B293 — resolution state of a planned session, for gating completion.
 *
 * `GET /api/week` resolves every session inline before responding, but a
 * resolution that throws leaves `resolved: null` + `resolve_error: true`
 * (A245 E-3/B17). The card used to render that as a bare "No exercises
 * resolved" placeholder with ACTIVE Done/Skip buttons — a completable empty
 * session. This helper is the single source of truth for "can this card be
 * completed / started":
 *
 *  - "ok"    → exercises (or blocks) are there, all actions available
 *  - "error" → resolution failed server-side; show retry, block completion
 *  - "empty" → resolved but genuinely zero content; explain, block completion
 *
 * Custom sessions carry their exercises inline and never touch the resolver.
 * Unresolved data self-heals on refetch: resolved payloads of non-completed
 * sessions are not persisted, so every week refetch re-runs resolution.
 */

export type ResolutionState = "ok" | "empty" | "error";

type ResolvedShape = {
  resolved_session?: {
    exercise_instances?: unknown[];
    blocks?: unknown[];
  };
};

export function sessionResolutionState(session: {
  is_custom?: boolean;
  resolve_error?: boolean;
  resolved?: Record<string, unknown> | null;
}): ResolutionState {
  if (session.is_custom) return "ok";
  const rs = (session.resolved as ResolvedShape | null | undefined)?.resolved_session;
  const hasContent =
    ((rs?.exercise_instances?.length ?? 0) > 0) || ((rs?.blocks?.length ?? 0) > 0);
  if (hasContent) return "ok";
  return session.resolve_error ? "error" : "empty";
}
