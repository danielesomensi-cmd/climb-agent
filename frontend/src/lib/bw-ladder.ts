/**
 * A298 — bodyweight ladders on the client: read-time badge data, the
 * post-feedback one-liners and the promotion tap.
 *
 * Nothing here decides a level: the server owns the closed loop
 * (`backend/engine/bw_progression.py`). The client only renders what the
 * server attached (`ladder` on custom rows, `suggested.bw_ladder.ladder` on
 * engine instances) and forwards the athlete's tap.
 */

import { toast } from "sonner";
import type { LadderInfo } from "@/lib/types";

export interface BwLadderUpdate {
  family?: string;
  ladder?: string;
  exercise_id?: string;
  kind?: string;
  message?: string;
}

/** Narrow an unknown payload to a LadderInfo (or undefined). */
export function asLadder(raw: unknown): LadderInfo | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const r = raw as Record<string, unknown>;
  if (typeof r.family !== "string" || typeof r.level_idx !== "number" || typeof r.n_levels !== "number") {
    return undefined;
  }
  return r as unknown as LadderInfo;
}

/** "Level 4/6 · Straddle L-sit" (1-based for humans). */
export function ladderTitle(l: LadderInfo): string {
  return `Level ${l.level_idx + 1}/${l.n_levels} · ${l.level_name}`;
}

/** Secondary line: band, next level, flags. */
export function ladderSubtitle(l: LadderInfo): string {
  const bits = [`band ${l.band}`];
  if (l.frozen) bits.push("doses frozen this phase");
  if (l.next_name) bits.push(l.manual_only_next ? `next: ${l.next_name} (manual only)` : `next: ${l.next_name}`);
  if (l.gate) bits.push(`needs ${l.gate.replace(/_/g, " ")}`);
  return bits.join(" · ");
}

/** The proposal sentence, or null. */
export function proposalText(l: LadderInfo): string | null {
  const p = l.proposal;
  if (!p) return null;
  return p.kind === "promotion" ? `Ready for ${p.to_name}: switch?` : `Your level is ${p.to_name}: switch?`;
}

/** Toast the ladder lines returned by POST /api/feedback (one toast). */
export function notifyBwLadderUpdates(raw: unknown): void {
  if (!Array.isArray(raw) || raw.length === 0) return;
  const lines = (raw as BwLadderUpdate[])
    .map((u) => u?.message)
    .filter((m): m is string => typeof m === "string" && m.length > 0);
  if (lines.length === 0) return;
  toast("Bodyweight levels", { description: lines.join("\n"), duration: 8000 });
}
