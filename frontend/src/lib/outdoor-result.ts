/**
 * B393 + A324 — one reading of an outdoor attempt, shared by every view.
 *
 * Frontend twin of `backend/engine/outdoor_attempt.py`. An attempt
 * (`routes[].attempts[]` of an outdoor log) carries:
 *
 * - `result`: `sent` | `fell` | `topped_out` | `aid`.
 *   `topped_out` (B393) = reached the top with rests on the rope (hangdog);
 *   `aid` (A324) = reached the top pulling on the gear (A0). Neither is a free
 *   ascent. `aid` exists only on a rope.
 * - `rope_role` (optional, A324): `lead` | `second` | `toprope`. Absent means
 *   lead — every log written before A324 is a lead log. The app never writes
 *   `lead` (see {@link withRopeRole}), so new lead logs stay identical to old ones.
 *
 * The single rule: a **send** is `sent` on lead ({@link isLeadSend}). `sent` on
 * second / top-rope is a clean ascent, **not** a send ({@link isCleanNonLead}):
 * blue «Second clean» / «TR clean», never green.
 *
 * Every helper takes the attempt itself. A bare `result` string is still
 * accepted (B393 signatures) and reads as lead — which is exactly why views
 * must pass the attempt: `attemptLabel(a.result)` would paint a clean second
 * green. A static scan (`b393-topped-out.test.ts`) forbids it in the views.
 */
import type { OutdoorAttempt, OutdoorRoute } from "@/lib/types";

export type AttemptResult = "sent" | "fell" | "topped_out" | "aid";
export type RopeRole = "lead" | "second" | "toprope";

export const ROPE_ROLES: readonly RopeRole[] = ["lead", "second", "toprope"];

/** What the helpers read: an attempt, or (legacy B393 signature) its bare result. */
export type AttemptLike =
  | { result?: string | null; rope_role?: string | null }
  | string
  | null
  | undefined;

function resultOf(a: AttemptLike): string | null {
  if (a == null) return null;
  if (typeof a === "string") return a;
  return a.result ?? null;
}

/** The attempt's rope role. Absent / unknown / bare result → `lead`. */
export function ropeRoleOf(a: AttemptLike): RopeRole {
  if (a == null || typeof a === "string") return "lead";
  const role = a.rope_role;
  return role === "second" || role === "toprope" ? role : "lead";
}

// ── Result-only predicates (B393). A string has no role: these say nothing
//    about who led. Views use the attempt-level helpers below. ──────────────

/** `result === "sent"`, role ignored. Use {@link isLeadSend} in views. */
export function isSendResult(result: string | undefined | null): boolean {
  return result === "sent";
}

export function isToppedResult(result: string | undefined | null): boolean {
  return result === "topped_out";
}

export function isAidResult(result: string | undefined | null): boolean {
  return result === "aid";
}

// ── Attempt-level reading (A324) ────────────────────────────────────────────

/** A send: `sent` on lead. The only result that counts as a send. */
export function isLeadSend(a: AttemptLike): boolean {
  return isSendResult(resultOf(a)) && ropeRoleOf(a) === "lead";
}

/** `sent` on second or top-rope: clean, but not a send. */
export function isCleanNonLead(a: AttemptLike): boolean {
  return isSendResult(resultOf(a)) && ropeRoleOf(a) !== "lead";
}

/** A0: to the top pulling on the gear (any rope role). */
export function isAid(a: AttemptLike): boolean {
  return isAidResult(resultOf(a));
}

export type AttemptKind = "send" | "clean_non_lead" | "topped" | "aid" | "fell";

export function attemptKind(a: AttemptLike): AttemptKind {
  const result = resultOf(a);
  if (isSendResult(result)) return ropeRoleOf(a) === "lead" ? "send" : "clean_non_lead";
  if (isToppedResult(result)) return "topped";
  if (isAidResult(result)) return "aid";
  return "fell";
}

/** Short role tag: «L», «2nd», «TR». */
export function ropeRoleShort(role: RopeRole): string {
  if (role === "second") return "2nd";
  if (role === "toprope") return "TR";
  return "L";
}

/** Long role name for titles and aria labels. */
export function ropeRoleName(role: RopeRole): string {
  if (role === "second") return "Second";
  if (role === "toprope") return "Top-rope";
  return "Lead";
}

/** Short label for a single attempt: «Sent», «Second clean», «TR clean»,
 *  «Top w/ rests», «A0», «Fell» — the last three with «(2nd)» / «(TR)» when
 *  not on lead. */
export function attemptLabel(a: AttemptLike): string {
  const role = ropeRoleOf(a);
  const suffix = role === "lead" ? "" : ` (${ropeRoleShort(role)})`;
  switch (attemptKind(a)) {
    case "send":
      return "Sent";
    case "clean_non_lead":
      return role === "toprope" ? "TR clean" : "Second clean";
    case "topped":
      return `Top w/ rests${suffix}`;
    case "aid":
      return `A0${suffix}`;
    default:
      return `Fell${suffix}`;
  }
}

/** The result word alone, for a badge drawn next to its role tag (edit
 *  form): «Sent» on lead, «Clean» on second / top-rope, «Top w/ rests», «A0»,
 *  «Fell». */
export function attemptResultLabel(a: AttemptLike): string {
  switch (attemptKind(a)) {
    case "send":
      return "Sent";
    case "clean_non_lead":
      return "Clean";
    case "topped":
      return "Top w/ rests";
    case "aid":
      return "A0";
    default:
      return "Fell";
  }
}

/** Background class for an attempt dot: green send, blue clean on
 *  second / top-rope, amber top with rests or A0, red fell. */
export function attemptBgClass(a: AttemptLike): string {
  switch (attemptKind(a)) {
    case "send":
      return "bg-success";
    case "clean_non_lead":
      return "bg-info";
    case "topped":
    case "aid":
      return "bg-warning";
    default:
      return "bg-danger";
  }
}

/** Text class for an attempt glyph. */
export function attemptTextClass(a: AttemptLike): string {
  switch (attemptKind(a)) {
    case "send":
      return "text-success";
    case "clean_non_lead":
      return "text-info";
    case "topped":
    case "aid":
      return "text-warning";
    default:
      return "text-danger";
  }
}

/** Tinted chip classes (border + background + text) for an attempt badge. */
export function attemptChipClass(a: AttemptLike): string {
  switch (attemptKind(a)) {
    case "send":
      return "border-success/40 bg-success/15 text-success";
    case "clean_non_lead":
      return "border-info/40 bg-info/15 text-info";
    case "topped":
    case "aid":
      return "border-warning/40 bg-warning/15 text-warning";
    default:
      return "border-danger/40 bg-danger/15 text-danger";
  }
}

/** Glyph for an attempt row: ✓ sent (green on lead, blue otherwise),
 *  ↑ top with rests, A0, ✗ fell. */
export function attemptGlyph(a: AttemptLike): string {
  switch (attemptKind(a)) {
    case "send":
    case "clean_non_lead":
      return "✓";
    case "topped":
      return "↑";
    case "aid":
      return "A0";
    default:
      return "✗";
  }
}

// ── Writing attempts ────────────────────────────────────────────────────────

/** The attempt with `role` set. Lead is written as ABSENT, like the backend
 *  stores it: a lead log stays identical to a pre-A324 one. */
export function withRopeRole<T extends OutdoorAttempt>(attempt: T, role: RopeRole): T {
  const next: OutdoorAttempt = { ...attempt };
  if (role === "lead") delete next.rope_role;
  else next.rope_role = role;
  return next as T;
}

/** Edit-form result cycle. On a rope: sent → fell → A0 → sent. On a boulder:
 *  sent ⇄ fell. A top with rests (B393) is never promoted by a tap: → fell. */
export function nextAttemptResult(result: string | undefined | null, onRope: boolean): AttemptResult {
  if (isSendResult(result)) return "fell";
  if (isToppedResult(result)) return "fell";
  if (result === "fell" && onRope) return "aid";
  return "sent"; // fell on a boulder, A0, anything unknown
}

/** Edit-form role cycle: Lead → 2nd → TR → Lead. */
export function nextRopeRole(role: RopeRole): RopeRole {
  if (role === "lead") return "second";
  if (role === "second") return "toprope";
  return "lead";
}

// ── Routes ──────────────────────────────────────────────────────────────────

type RouteLike = { attempts?: AttemptLike[] | null; discipline?: string | null };

/** The route has at least one send (`sent` on lead). */
export function routeLeadSent(route: RouteLike): boolean {
  return (route.attempts ?? []).some(isLeadSend);
}

/** No send, but at least one clean ascent on second / top-rope. Exclusive
 *  with {@link routeLeadSent} (backend `route_clean_non_lead`). */
export function routeCleanNonLead(route: RouteLike): boolean {
  const attempts = route.attempts ?? [];
  return !attempts.some(isLeadSend) && attempts.some(isCleanNonLead);
}

/** No `sent` at all (any role), but at least one A0 (backend `route_aid`). */
export function routeAid(route: RouteLike): boolean {
  const attempts = route.attempts ?? [];
  return !attempts.some((a) => isSendResult(resultOf(a))) && attempts.some(isAid);
}

/** The role of the route's first clean non-lead ascent («Second clean» vs
 *  «TR clean»), or null. */
export function routeCleanRole(route: RouteLike): RopeRole | null {
  const clean = (route.attempts ?? []).find(isCleanNonLead);
  return clean ? ropeRoleOf(clean) : null;
}

/** A boulder problem: its own discipline, else the session's when the route
 *  carries none (backend `is_boulder_route`). */
export function isBoulderRoute(route: RouteLike, sessionDiscipline: string | null | undefined): boolean {
  if (route.discipline) return route.discipline === "boulder";
  return sessionDiscipline === "boulder";
}

/** A boulder has no rope: drop every role, A0 → fell (what the backend does
 *  on save). Returns the same route object when nothing changes. */
export function stripRopeOnly<R extends OutdoorRoute>(route: R): R {
  const changed = route.attempts.some((a) => a.rope_role !== undefined || isAidResult(a.result));
  if (!changed) return route;
  const attempts = route.attempts.map((a) => {
    const next: OutdoorAttempt = { ...a, result: isAidResult(a.result) ? "fell" : a.result };
    delete next.rope_role;
    return next;
  });
  return { ...route, attempts };
}

/** The rope role of the most recent attempt across `routes` (by `logged_at`
 *  when present, else the last attempt of the last route), or null when no
 *  attempt was logged. The live logger starts from it after a reload, so a
 *  reloaded PWA does not silently go back to Lead in the middle of a day on
 *  second (A324). */
export function lastAttemptRopeRole(
  routes: ReadonlyArray<{ attempts?: ReadonlyArray<{ result?: string; rope_role?: string; logged_at?: string }> | null }>,
): RopeRole | null {
  let best: { ms: number; order: number; role: RopeRole } | null = null;
  let order = 0;
  for (const r of routes) {
    for (const a of r.attempts ?? []) {
      order += 1;
      const ms = a.logged_at ? Date.parse(a.logged_at) : NaN;
      const key = Number.isFinite(ms) ? ms : -Infinity;
      if (!best || key > best.ms || (key === best.ms && order > best.order)) {
        best = { ms: key, order, role: ropeRoleOf(a) };
      }
    }
  }
  return best ? best.role : null;
}
