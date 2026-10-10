/**
 * A300 + A301 — the alerts of a week, for the UI. Pure, no React.
 *
 * Daniele's decision (2026-10-05): "se voglio fare sovrallenamento lo faccio,
 * decisione mia, tu solo segnala alert". After a user action the backend no
 * longer downshifts, ripples or compensates anything: it returns
 * `guard_warnings` (A301, a sibling of `week_plan` on `GET /api/week` and on
 * every replanner response, never persisted) and, for the complementary lunch
 * slots, `week_plan.secondary_warnings` / `week_plan.unmet_secondary` (A300).
 *
 * This module turns those three lists into what the screens show: a badge and
 * a line per session, and a list for the week. Nothing here can change the
 * plan, and no text may suggest that something was blocked or downgraded.
 */
import type {
  DayPlan,
  FocusFamily,
  GuardWarning,
  SecondaryWarning,
  SessionSlot,
  UnmetSecondary,
  WeekPlan,
} from "@/lib/types";

/** One alert line on a session card or in a list. */
export interface SessionAlert {
  /** "guard" = A301 recovery guard, "structure" = A300 lunch placement rule. */
  source: "guard" | "structure";
  code: string;
  title: string;
  message: string;
  date: string;
  slot: string | null;
  session_id: string | null;
}

export const FOCUS_LABELS: Record<FocusFamily, string> = {
  legs: "Legs",
  hiit: "HIIT (treadmill)",
  z2: "Zone 2 cardio (treadmill)",
  upper_push_arms: "Push + arms (biceps incl.)",
};

export const FOCUS_ORDER: FocusFamily[] = ["legs", "hiit", "z2", "upper_push_arms"];

export function focusLabel(focus: string | null | undefined): string {
  if (!focus) return "Complementary";
  return FOCUS_LABELS[focus as FocusFamily] ?? focus;
}

const GUARD_TITLES: Record<string, string> = {
  finger_gap: "Finger gap under 48 h",
  finger_test_72h: "Hard fingers before a finger test",
  heavy_pull_7d: "Many heavy-pull days in 7",
  hiit_near_max: "HIIT next to a max day",
  hard_cap: "Above your weekly hard-day cap",
  pre_trip: "Hard session before a trip",
  post_outdoor: "Right after a big outdoor day",
  hard_back_to_back: "Back-to-back hard days",
};

export function guardTitle(code: string): string {
  return GUARD_TITLES[code] ?? "Recovery alert";
}

const STRUCTURE_TITLES: Record<string, string> = {
  hiit_near_max: "HIIT next to a max day",
  biceps_before_heavy_pull: "Biceps before heavy pulling",
  legs_before_limit: "Legs before a limit / outdoor day",
  pretrip_no_hard: "Hard lunch before a trip",
  hiit_weekly_cap: "More than one HIIT this week",
};

function withText(refs: string[] | undefined): string {
  return refs && refs.length ? ` (${refs.join(", ")})` : "";
}

function structureMessage(w: SecondaryWarning): string {
  const what = w.session_id ?? focusLabel(w.focus);
  switch (w.code) {
    case "hiit_near_max":
      return `${what} on ${w.date} is HIIT on the day of, or the day before, a max session${withText(w.with)}.`;
    case "biceps_before_heavy_pull":
      return `${what} on ${w.date} trains biceps within 24 h before heavy pulling${withText(w.with)}.`;
    case "legs_before_limit":
      return `${what} on ${w.date} loads the legs within 48 h before a limit or outdoor day${withText(w.with)}.`;
    case "pretrip_no_hard":
      return `${what} on ${w.date} is a demanding lunch on a pre-trip easy day.`;
    case "hiit_weekly_cap":
      return `${what} on ${w.date} is a second HIIT this week (the rotation plans at most one).`;
    default:
      return `${what} on ${w.date}: ${w.code}${withText(w.with)}.`;
  }
}

export function guardAlert(w: GuardWarning): SessionAlert {
  return {
    source: "guard",
    code: w.code,
    title: guardTitle(w.code),
    message: w.message,
    date: w.date,
    slot: w.slot ?? null,
    session_id: w.session_id ?? null,
  };
}

export function structureAlert(w: SecondaryWarning): SessionAlert {
  return {
    source: "structure",
    code: w.code,
    title: STRUCTURE_TITLES[w.code] ?? "Lunch rotation alert",
    message: structureMessage(w),
    date: w.date,
    slot: w.slot ?? null,
    session_id: w.session_id ?? null,
  };
}

/** One line per `unmet_secondary` item — never an error, the slot is just free. */
export function describeUnmetSecondary(u: UnmetSecondary): string {
  const where = u.date ? `${u.date}${u.slot ? ` ${u.slot}` : ""}` : "";
  switch (u.reason) {
    case "rotation_overflow":
      return `${focusLabel(u.focus)} found no free complementary slot this week.`;
    case "no_focus":
      return `${where}: complementary slot left free — no focus family is selected.`;
    case "rotation_exhausted":
      return `${where}: complementary slot left free — the rotation has fewer families than slots.`;
    case "no_session_fits":
      return `${where}: no ${focusLabel(u.focus)} session fits the slot (equipment or time limit).`;
    default:
      return `${where || "This week"}: a complementary slot stayed free (${u.reason}).`;
  }
}

// ---------------------------------------------------------------------------
// Matching
// ---------------------------------------------------------------------------

function days(plan: WeekPlan | null | undefined): DayPlan[] {
  return plan?.weeks?.[0]?.days ?? [];
}

function matches(
  a: { date: string; slot: string | null; session_id: string | null },
  date: string,
  slot: string | null | undefined,
  sessionId: string | null | undefined,
): boolean {
  if (a.date !== date) return false;
  if (a.slot != null && slot != null && a.slot !== slot) return false;
  if (a.session_id != null && sessionId != null && a.session_id !== sessionId) return false;
  return true;
}

function sessionStillOpen(plan: WeekPlan, ref: { date: string; slot: string | null; session_id: string | null }): boolean {
  const day = days(plan).find((d) => d.date === ref.date);
  if (!day) return false;
  return (day.sessions ?? []).some(
    (s) =>
      s.status !== "done" &&
      s.status !== "skipped" &&
      (ref.slot == null || s.slot === ref.slot) &&
      (ref.session_id == null || s.session_id === ref.session_id),
  );
}

/**
 * The cached guard alerts that still describe a session of *plan*. Used when a
 * response changed the plan but did not carry fresh `guard_warnings` (exercise
 * edits, surface override): a removed or completed session loses its badge
 * instead of keeping a stale one. The next `GET /api/week` recomputes them all.
 */
export function pruneGuardWarnings(warnings: GuardWarning[], plan: WeekPlan): GuardWarning[] {
  return warnings.filter((w) => sessionStillOpen(plan, w));
}

/**
 * The structure alerts not already said by a guard alert. `guards_v1` and the
 * lunch rotation both emit `hiit_near_max` for the same HIIT lunch: shown once,
 * as the guard alert (same code, date, slot and session).
 */
function dedupeStructure(guards: SessionAlert[], structure: SessionAlert[]): SessionAlert[] {
  const key = (a: SessionAlert) => `${a.code}|${a.date}|${a.slot ?? ""}|${a.session_id ?? ""}`;
  const said = new Set(guards.map(key));
  return structure.filter((a) => !said.has(key(a)));
}

/** Every alert of one session (guard first, then lunch rules), stable order. */
export function alertsForSession(
  guardWarnings: GuardWarning[] | null | undefined,
  plan: WeekPlan | null | undefined,
  date: string,
  session: Pick<SessionSlot, "slot" | "session_id" | "status">,
): SessionAlert[] {
  if (session.status === "done" || session.status === "skipped") return [];
  const guards = (guardWarnings ?? [])
    .filter((w) => matches(w, date, session.slot, session.session_id))
    .map(guardAlert);
  const structure = (plan?.secondary_warnings ?? [])
    .filter((w) => matches(w, date, session.slot, session.session_id))
    .map(structureAlert);
  return [...guards, ...dedupeStructure(guards, structure)];
}

/** All alerts of the week, in date / slot order (guard alerts before lunch rules on ties). */
export function weekAlerts(
  guardWarnings: GuardWarning[] | null | undefined,
  plan: WeekPlan | null | undefined,
  onlyDate?: string,
): SessionAlert[] {
  const slotIdx = (s: string | null) => (s === "morning" ? 0 : s === "lunch" ? 1 : s === "evening" ? 2 : 3);
  const guards = (guardWarnings ?? []).map(guardAlert);
  const all = [
    ...guards,
    ...dedupeStructure(guards, (plan?.secondary_warnings ?? []).map(structureAlert)),
  ].filter((a) => !onlyDate || a.date === onlyDate);
  return all
    .map((a, i) => ({ a, i }))
    .sort((x, y) =>
      x.a.date.localeCompare(y.a.date) ||
      slotIdx(x.a.slot) - slotIdx(y.a.slot) ||
      (x.a.source === y.a.source ? 0 : x.a.source === "guard" ? -1 : 1) ||
      x.i - y.i,
    )
    .map(({ a }) => a);
}

/**
 * A308 — the alerts of *date* that no session card of that day shows inline
 * (`alertsForSession`). /today lists only these in the day's alerts card, so
 * each alert is said once: next to its session when it has one, in the card
 * otherwise.
 */
export function alertsOffSessions(
  guardWarnings: GuardWarning[] | null | undefined,
  plan: WeekPlan | null | undefined,
  date: string,
): SessionAlert[] {
  const key = (a: SessionAlert) => `${a.source}|${a.code}|${a.date}|${a.slot ?? ""}|${a.session_id ?? ""}`;
  const day = days(plan).find((d) => d.date === date);
  const inline = new Set(
    (day?.sessions ?? []).flatMap((s) => alertsForSession(guardWarnings, plan, date, s)).map(key),
  );
  return weekAlerts(guardWarnings, plan, date).filter((a) => !inline.has(key(a)));
}

/** The guard alerts a mutation response carries, if any (undefined = not in the response). */
export function guardWarningsOf(result: unknown): GuardWarning[] | undefined {
  if (!result || typeof result !== "object") return undefined;
  const gw = (result as { guard_warnings?: unknown }).guard_warnings;
  return Array.isArray(gw) ? (gw as GuardWarning[]) : undefined;
}

/**
 * The messages of the alerts that involve the session at *date* / *slot* —
 * flagged on it, or naming it in `with` (mirror of backend `guards_v1.involves`).
 * Used after an insertion whose response carries only `guard_warnings`.
 */
export function alertMessagesFor(
  warnings: GuardWarning[] | null | undefined,
  date: string,
  slot?: string | null,
): string[] {
  const hit = (d: string | null | undefined, s: string | null | undefined) =>
    d === date && (slot == null || s == null || s === slot);
  return (warnings ?? [])
    .filter((w) => hit(w.date, w.slot) || (w.with ?? []).some((r) => hit(r.date, r.slot)))
    .map((w) => w.message);
}

/**
 * The toast after a user action that went through with alerts (quick-add,
 * override): the action is applied as asked; this only says what to watch.
 * Null when there is nothing to say.
 */
export function describeActionAlerts(
  messages: string[] | null | undefined,
  verb: "Added" | "Changed" | "Moved" = "Added",
): { title: string; description: string } | null {
  const lines = Array.from(new Set((messages ?? []).filter((m) => typeof m === "string" && m.trim())));
  if (lines.length === 0) return null;
  return {
    title: lines.length === 1 ? `${verb} — 1 alert` : `${verb} — ${lines.length} alerts`,
    description: `${lines.join(" ")} Your call: nothing else in the plan was changed.`,
  };
}

// ---------------------------------------------------------------------------
// User-owned sessions (mirror of backend/engine/user_owned.py)
// ---------------------------------------------------------------------------

export const USER_MARKERS = new Set([
  "quick_add",
  "user_forced",
  "manual_override",
  "key_reschedule",
  "custom_add",
  "generated_add",
  "user_moved",
]);

/** True when the user put, forced, moved or edited this session (B369 `is_user_owned`). */
export function isUserOwned(s: Partial<SessionSlot> | null | undefined): boolean {
  if (!s) return false;
  if (s.forced || s.is_custom || s._user_edited) return true;
  return (s.constraints_applied ?? []).some((m) => USER_MARKERS.has(m));
}

export interface KeptSession {
  date: string;
  slot: string;
  name: string;
}

/**
 * The user's own sessions still planned from *today* on — what a regeneration
 * (availability save, structure change) carried over instead of replacing.
 */
export function keptUserSessions(plan: WeekPlan | null | undefined, today: string): KeptSession[] {
  const out: KeptSession[] = [];
  for (const day of days(plan)) {
    if (day.date < today) continue;
    for (const s of day.sessions ?? []) {
      if (s.status === "done" || s.status === "skipped") continue;
      if (!isUserOwned(s)) continue;
      out.push({ date: day.date, slot: s.slot, name: s.name || s.session_id.replace(/_/g, " ") });
    }
  }
  return out;
}

/** The toast after "Save & regenerate": what of the user's was kept. */
export function describeKeptSessions(kept: KeptSession[]): string {
  if (kept.length === 0) return "No sessions of yours were planned from today on — nothing to keep.";
  const list = kept.map((k) => `${k.name} (${k.date} ${k.slot})`).join(", ");
  return kept.length === 1
    ? `Kept your session: ${list}.`
    : `Kept your ${kept.length} sessions: ${list}.`;
}

/** The note under the availability editor, before saving: what will be kept. */
export function describeKeptPreview(kept: KeptSession[]): string {
  if (kept.length === 0) return "You have no sessions of your own planned from today on.";
  const list = kept.map((k) => `${k.name} (${k.date} ${k.slot})`).join(", ");
  return kept.length === 1 ? `Your session stays: ${list}.` : `Your ${kept.length} sessions stay: ${list}.`;
}
