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
import { FOCUS_FAMILIES } from "@/lib/slot-structure";
import { formatSessionId, shortDay } from "@/lib/key-sessions";

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
  arms_shoulders: "Arms, shoulders + handstand",
};

/** Display order of the family pickers: every family, the opt-in one last. */
export const FOCUS_ORDER: FocusFamily[] = FOCUS_FAMILIES;

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
  // B372-FE-COPY (B414): since B372 post_outdoor follows EVERY outdoor day
  // that counts (planned, logged hard, big load, no route log) — the reason
  // is in the message, so the title no longer says "big".
  post_outdoor: "After an outdoor day",
  hard_back_to_back: "Back-to-back hard days",
  // A330 (D288-FE) — the A327 codes, named as in the user guide.
  finger_low_gap: "Light finger work too close",
  finger_hard_cap: "Above the weekly finger-hard cap",
  max_hang_cap: "Above the weekly max-hang cap",
  crag_block: "After a crag block",
};

/** A330 — `crag_block` says which of its three rules the session breaks. */
const CRAG_BLOCK_TITLES: Record<string, string> = {
  rest_day: "Rest day after a crag block",
  no_hard: "No hard session after a crag block",
  finger_72h: "Fingers wait after a crag block",
};

/** Mirror of `retest_policy.FINGER_LOW_MAX_PER_DAY` (light finger sessions a day). */
export const FINGER_LOW_MAX_PER_DAY = 2;

export function guardTitle(code: string, detail?: string | null): string {
  if (code === "crag_block" && detail && CRAG_BLOCK_TITLES[detail]) return CRAG_BLOCK_TITLES[detail];
  return GUARD_TITLES[code] ?? "Recovery alert";
}

// ---------------------------------------------------------------------------
// A330 (D288-FE) — the app's own text for the A327 codes, built from the
// payload fields (`count`, `cap`, `detail`, `crag_days`, `finger_ok_from`,
// `gap_h`, `low_count`). A field missing (an older server) → the backend's
// `message`, as before. Informative only: nothing here says a session was
// blocked or changed.
// ---------------------------------------------------------------------------

const isIsoDay = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** "Limit boulder gym" — the session's display name, else its id made readable. */
function sessionName(w: GuardWarning): string {
  return (w.name && w.name.trim()) || formatSessionId(w.session_id);
}

/** "Sat 7 Nov – Sun 8 Nov" (two or more days), or the one day. */
function dayRange(days: string[]): string {
  const sorted = [...days].filter(isIsoDay).sort();
  if (sorted.length === 0) return "";
  const first = shortDay(sorted[0].slice(0, 10));
  const last = shortDay(sorted[sorted.length - 1].slice(0, 10));
  return sorted.length === 1 ? first : `${first} – ${last}`;
}

/** "Wed 11 Nov, 18:00" from "2026-11-11T18:00". */
function clockLabel(iso: string): string {
  const day = shortDay(iso.slice(0, 10));
  const hm = /T(\d{2}:\d{2})/.exec(iso)?.[1];
  return hm ? `${day}, ${hm}` : day;
}

const slotOrder = (s: string | null | undefined) =>
  s === "morning" ? 0 : s === "lunch" ? 1 : s === "evening" ? 2 : 3;

/** 6 → "6", 7.5 → "7.5". */
function hours(h: number): string {
  return String(Math.round(h * 10) / 10);
}

/**
 * The other side of a `finger_low_gap` pair: the nearest `with` ref at or
 * before the flagged session (the later of a pair is the one flagged; a crag
 * day has no slot and runs 08-18).
 */
function partnerLabel(w: GuardWarning): string | null {
  const refs = (w.with ?? []).filter((r) => isIsoDay(r.date));
  const before = refs.filter(
    (r) => r.date < w.date || (r.date === w.date && (!r.session_id || slotOrder(r.slot) <= slotOrder(w.slot))),
  );
  const pool = before.length ? before : refs;
  const p = pool[pool.length - 1];
  if (!p) return null;
  if (!p.session_id) return `your crag day on ${shortDay(p.date.slice(0, 10))}`;
  const when = p.date === w.date ? "same day" : shortDay(p.date.slice(0, 10));
  return `${formatSessionId(p.session_id)} (${when}${p.slot ? `, ${p.slot}` : ""})`;
}

/** The app's message for a guard alert (the backend's for the codes it does not word). */
export function guardMessage(w: GuardWarning): string {
  const name = sessionName(w);
  const day = isIsoDay(w.date) ? shortDay(w.date.slice(0, 10)) : w.date;
  switch (w.code) {
    case "finger_hard_cap":
      if (isNum(w.count) && isNum(w.cap)) {
        return `This week has ${w.count} finger-hard days, crag days included; the cap is ${w.cap}. ${name} on ${day} is past it.`;
      }
      break;
    case "max_hang_cap":
      if (isNum(w.count) && isNum(w.cap)) {
        return `This week has ${w.count} max-hang days; the cap is ${w.cap}. ${name} on ${day} is past it.`;
      }
      break;
    case "crag_block": {
      const crag = w.crag_days ?? [];
      if (crag.length < 2) break;
      const block = `${crag.length} hard crag days in a row (${dayRange(crag)})`;
      if (w.detail === "rest_day") {
        return `After ${block}, ${day} is meant as a true rest day: ${name} is planned on it. A lunch extra or recovery / prehab is fine.`;
      }
      if (w.detail === "no_hard") {
        return `${day} is the second day after ${block}: no hard session that day, and ${name} is a hard one.`;
      }
      if (w.detail === "finger_72h" && isIsoDay(w.finger_ok_from)) {
        const at = w.slot ? ` (${w.slot})` : "";
        return `After ${block}, hard finger work only from ${clockLabel(w.finger_ok_from)} (72 h after the crag): ${name} on ${day}${at} comes earlier.`;
      }
      break;
    }
    case "finger_low_gap":
      if (w.detail === "gap" && isNum(w.gap_h)) {
        const other = partnerLabel(w);
        if (other) {
          return `${name} on ${day} is less than ${hours(w.gap_h)} h from ${other}: a light finger session needs ${hours(w.gap_h)} h from any other finger session.`;
        }
      }
      if (w.detail === "per_day" && isNum(w.low_count)) {
        return `${day} has ${w.low_count} light finger sessions, at most ${FINGER_LOW_MAX_PER_DAY} a day: ${name} is one too many.`;
      }
      break;
  }
  return w.message;
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
      return `${what} on ${w.date} is HIIT less than 24 h before a max session${withText(w.with)}.`;
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
    title: guardTitle(w.code, w.detail),
    message: guardMessage(w),
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
    .map((w) => guardMessage(w));
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
