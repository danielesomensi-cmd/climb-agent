// A294 — pure helpers over the key-session status (`key_status`, a sibling of
// `week_plan` in the week / replanner responses). No React, no I/O.
import type { KeyConflict, KeyRequirement, KeySessionRole, KeyStatus } from "@/lib/types";

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
  return status.sessions.find((s) => s.date === date && (s.slot ?? null) === (slot ?? null)) ?? null;
}

/** Days of the week with a key session (for the week-grid marker). */
export function keyDays(status: KeyStatus | null | undefined): Record<string, "key" | "lost"> {
  const out: Record<string, "key" | "lost"> = {};
  for (const s of status?.sessions ?? []) {
    if (s.role === "key") out[s.date] = out[s.date] === "lost" ? "lost" : "key";
    if ((s.role === "skipped" || s.role === "downgraded") && s.keys.length > 0) out[s.date] = "lost";
  }
  return out;
}

/** "Fri 09/10" from an ISO date (local, no timezone shift). */
export function shortDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date(y, m - 1, d).getDay()];
  return `${wd} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
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
      return "Done";
    case "planned":
      return nextPlanned ? `Next: ${shortDay(nextPlanned.date)}` : "Planned";
    case "not_due":
      return r.due_by ? `Not due — next one by ${shortDay(r.due_by)}` : "Not due this week";
    case "unplaceable":
      return "The plan could not fit it this week";
    case "partial":
    case "missing": {
      const prefix = r.status === "partial" ? "Only a partial dose" : "Missing";
      switch (r.resolution) {
        case "proposal":
          return `${prefix} — catch-up proposed below`;
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
 *  A294 review: a high `finger_gap` too — finger-hard work inside the recovery
 *  gap of a finger-hard day nobody can move (a done key session included). */
export function blockingConflicts(conflicts: KeyConflict[] | undefined): KeyConflict[] {
  return (conflicts ?? []).filter(
    (c) =>
      ["key_removed", "key_replaced", "test_downgraded", "pre_test_fatigue"].includes(c.code) ||
      (c.code === "finger_gap" && c.severity === "high"),
  );
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
