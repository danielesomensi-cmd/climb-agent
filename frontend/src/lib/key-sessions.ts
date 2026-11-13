// A294 — pure helpers over the key-session status (`key_status`, a sibling of
// `week_plan` in the week / replanner responses). No React, no I/O.
import type {
  KeyConflict,
  KeyProposal,
  KeyProposalSideEffect,
  KeyRequirement,
  KeySessionRole,
  KeyStatus,
} from "@/lib/types";

const KEY_LABELS: Record<string, string> = {
  finger_max: "Finger max",
  finger_maintenance: "Finger maintenance",
  limit_power: "Limit",
  pulling_max: "Max pulling",
  power_endurance: "PE intervals",
  project: "Project",
  technique: "Technique",
  try_hard: "Try-hard",
};

export function keyLabel(key: string): string {
  return KEY_LABELS[key] ?? key.replace(/_/g, " ");
}

/** The role of the session in (date, slot), or null when it carries no key stimulus. */
export function keyRoleFor(
  status: KeyStatus | null | undefined,
  date: string,
  slot: string | null | undefined,
): KeySessionRole | null {
  if (!status?.sessions) return null;
  const role = status.sessions.find((s) => s.date === date && (s.slot ?? null) === (slot ?? null)) ?? null;
  // B374: a skipped / downgraded key whose stimulus is still covered this week
  // (re-scheduled, or another key session carries it) is not a loss — no badge.
  if (role && (role.role === "skipped" || role.role === "downgraded") && !isKeyLost(status, role)) return null;
  return role;
}

/**
 * B374 — a skipped / downgraded key session is "lost" only when one of its
 * stimuli is still owed this week. When the key was moved (or another session
 * of the week delivers it) its requirement carries no debt: the star follows
 * the session to its new day and the old day shows nothing.
 * A key with no requirement row stays lost (conservative).
 */
export function isKeyLost(status: KeyStatus | null | undefined, role: KeySessionRole): boolean {
  if (role.keys.length === 0) return false;
  const reqs = status?.requirements ?? [];
  return role.keys.some((k) => {
    const r = reqs.find((x) => x.key === k);
    return !r || (r.debt ?? 0) > 0;
  });
}

/** Days of the week with a key session (for the week-grid marker). */
export function keyDays(status: KeyStatus | null | undefined): Record<string, "key" | "lost"> {
  const out: Record<string, "key" | "lost"> = {};
  for (const s of status?.sessions ?? []) {
    if (s.role === "key") out[s.date] = out[s.date] === "lost" ? "lost" : "key";
    if ((s.role === "skipped" || s.role === "downgraded") && isKeyLost(status, s)) out[s.date] = "lost";
  }
  return out;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parseIso(iso: string): { y: number; m: number; d: number } | null {
  const [y, m, d] = iso.split("-").map(Number);
  return y && m && d ? { y, m, d } : null;
}

/** "Fri 9 Oct" from an ISO date (local, no timezone shift). A325: the month by
 *  name — "10/11" reads as 10 November or as October 11 depending on the reader. */
export function shortDay(iso: string): string {
  const p = parseIso(iso);
  if (!p) return iso;
  return `${WEEKDAYS[new Date(p.y, p.m - 1, p.d).getDay()]} ${p.d} ${MONTHS[p.m - 1]}`;
}

/** "Mon" from an ISO date. */
export function weekdayOf(iso: string): string {
  const p = parseIso(iso);
  return p ? WEEKDAYS[new Date(p.y, p.m - 1, p.d).getDay()] : iso;
}

/**
 * A325 — when a session takes place, the way one would say it: "tonight",
 * "today (lunch)", "tomorrow (evening)", else "Thu 12 Nov (evening)".
 */
export function whenLabel(iso: string, slot: string | null | undefined, today: string = localToday()): string {
  const slotPart = slot ? ` (${slot})` : "";
  if (iso === today) return slot === "evening" ? "tonight" : `today${slotPart}`;
  const t = parseIso(today);
  if (t) {
    const next = new Date(t.y, t.m - 1, t.d + 1);
    if (iso === localToday(next)) return `tomorrow${slotPart}`;
  }
  return `${shortDay(iso)}${slotPart}`;
}

/**
 * A325 — the session a re-schedule proposal takes the place of: the side
 * effect on the proposal's own day and slot. Said once ("Swap A for B"),
 * never as a headline plus an "also changes" that repeats it.
 */
export function replacedBy(p: KeyProposal): KeyProposalSideEffect | null {
  return (
    p.side_effects.find(
      (s) => s.date === p.date && s.slot === p.slot && s.to === p.session_id && !!s.from && s.from !== s.to,
    ) ?? null
  );
}

/** A325 — "1 of 2 drills done on Mon, Hard Target still to do" (technique only), or null. */
export function techniqueProgressLine(r: KeyRequirement): string | null {
  const pr = r.progress;
  if (!pr || pr.done <= 0) return null;
  const days = [...new Set(r.partial.map((x) => weekdayOf(x.date)))];
  const on = days.length === 1 ? ` on ${days[0]}` : "";
  const missed = pr.drills_missed.map((d) => d.name).join(", ");
  const left = pr.needed - pr.done;
  return `${pr.done} of ${pr.needed} drills done${on}${missed ? `, ${missed} still to do` : `, ${left} more to do`}`;
}

/** A329 — the technique metrics an outdoor day is logged with: [one, many]. */
const TECHNIQUE_METRIC_TEXT: Record<string, [string, string]> = {
  foot_slips_per_go: ["foot slip per go", "foot slips per go"],
  sample_readjust: ["foot readjustment on a sample pitch", "foot readjustments on a sample pitch"],
};

/** 2 → "2", 1.5 → "1.5", 1.333 → "1.33". */
function formatValue(v: number): string {
  return String(Math.round(v * 100) / 100);
}

/**
 * A330 (D288-FE) — technique ticked by a crag day with a logged target (A329):
 * "done outdoors: 2 foot slips per go (Isatis L1)", or null when the key was
 * not done that way.
 */
export function outdoorTechniqueLine(r: KeyRequirement): string | null {
  if (r.status !== "done") return null;
  const tt = r.done.find((x) => x.technique_target)?.technique_target;
  if (!tt || typeof tt.value !== "number" || !Number.isFinite(tt.value)) return null;
  const [one, many] = TECHNIQUE_METRIC_TEXT[tt.metric] ?? [String(tt.metric).replace(/_/g, " "), String(tt.metric).replace(/_/g, " ")];
  const sample = tt.sample?.trim();
  return `done outdoors: ${formatValue(tt.value)} ${tt.value === 1 ? one : many}${sample ? ` (${sample})` : ""}`;
}

export function formatSessionId(id: string | null | undefined): string {
  if (!id) return "session";
  const s = id.replace(/^custom_/, "").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** One line of the debt card for a requirement. */
export function requirementLine(r: KeyRequirement): string {
  const nextPlanned = r.planned.find((p) => !p.unmarked);
  switch (r.status) {
    case "done":
      return outdoorTechniqueLine(r) ?? "Done";
    case "planned": {
      // A325: the missing drill sits in a planned session (a top-up).
      const drill = nextPlanned?.topup ? nextPlanned.drills?.map((d) => d.name).join(", ") : "";
      if (nextPlanned && drill) return `${drill} added to ${shortDay(nextPlanned.date)}'s session`;
      return nextPlanned ? `Next: ${shortDay(nextPlanned.date)}` : "Planned";
    }
    case "not_due":
      return r.due_by ? `Not due — next one by ${shortDay(r.due_by)}` : "Not due this week";
    case "unplaceable":
      return "The plan could not fit it this week";
    case "partial":
    case "missing": {
      // A325: say WHY — which drills counted and which is still owed.
      const prefix = techniqueProgressLine(r) ?? (r.status === "partial" ? "Only a partial dose" : "Missing");
      switch (r.resolution) {
        case "proposal":
          return `${prefix} — catch-up proposed below`;
        case "topup":
          return `${prefix} — one-tap add below`;
        case "deferred_next":
          return r.next_key?.date
            ? `${prefix} — next key session ${shortDay(r.next_key.date)}, no catch-up this week`
            : `${prefix} — wait for next week's key session`;
        case "deferred_fatigue":
          return `${prefix} — no catch-up: you logged a very hard session recently`;
        case "let_go":
          return `${prefix} — no safe day left this week, let it go`;
        case "missed":
          return `${prefix} — the week is over`;
        default:
          return r.hint ? `${prefix} — ${r.hint}` : prefix;
      }
    }
    default:
      return r.status;
  }
}

/** Whether the card has anything worth interrupting the athlete for. */
export function hasKeyIssues(status: KeyStatus | null | undefined): boolean {
  if (!status) return false;
  return (status.summary?.debt ?? 0) > 0 || (status.conflicts?.length ?? 0) > 0;
}

/** Conflicts of an insertion that deserve a confirm (dry run of a custom session).
 *  A301-FE: only the ones about the user's key session itself (`key_removed`,
 *  `key_replaced`). Recovery-guard codes (`finger_gap`, `pre_test_fatigue`,
 *  `test_downgraded`) never interrupt an insertion — "tu solo segnala alert":
 *  they surface afterwards as the post-insert alert toast and the
 *  `guard_warnings` badge on the session. */
export function blockingConflicts(conflicts: KeyConflict[] | undefined): KeyConflict[] {
  return (conflicts ?? []).filter((c) => c.code === "key_removed" || c.code === "key_replaced");
}

/** localStorage key for "dismissed this week" (per stimulus). */
export function dismissKey(weekStart: string, stimulus: string): string {
  return `climb_key_dismiss:${weekStart}:${stimulus}`;
}

export function readDismissed(weekStart: string, stimulus: string): boolean {
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(dismissKey(weekStart, stimulus)) === "1";
  } catch {
    return false;
  }
}

export function writeDismissed(weekStart: string, stimulus: string): void {
  try {
    window.localStorage.setItem(dismissKey(weekStart, stimulus), "1");
  } catch {
    /* private mode / blocked storage: the dismiss just does not stick */
  }
}

/** Client-local YYYY-MM-DD (the server's clock is UTC). */
export function localToday(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
