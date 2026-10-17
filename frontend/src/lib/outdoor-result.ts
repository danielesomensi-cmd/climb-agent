/**
 * B393 — one reading of an outdoor attempt's `result`, shared by every view.
 *
 * `topped_out` = reached the top with rests (hangdog, top-rope, in pieces).
 * It is NOT a send: the engine already reads it that way (athlete_context,
 * grade_evidence, milestones), the app used to paint it green as «Sent».
 */
export type AttemptResult = "sent" | "fell" | "topped_out";

/** Only a clean ascent counts as a send. */
export function isSendResult(result: string | undefined | null): boolean {
  return result === "sent";
}

export function isToppedResult(result: string | undefined | null): boolean {
  return result === "topped_out";
}

/** Short label for a single attempt. */
export function attemptLabel(result: string | undefined | null): string {
  if (isSendResult(result)) return "Sent";
  if (isToppedResult(result)) return "Top w/ rests";
  return "Fell";
}

/** Background class for an attempt dot / badge: green sent, amber top with rests, red fell. */
export function attemptBgClass(result: string | undefined | null): string {
  if (isSendResult(result)) return "bg-success";
  if (isToppedResult(result)) return "bg-warning";
  return "bg-danger";
}

/** Text class for an attempt glyph. */
export function attemptTextClass(result: string | undefined | null): string {
  if (isSendResult(result)) return "text-success";
  if (isToppedResult(result)) return "text-warning";
  return "text-danger";
}

/** Glyph for an attempt row: ✓ sent, ↑ top with rests, ✗ fell. */
export function attemptGlyph(result: string | undefined | null): string {
  if (isSendResult(result)) return "✓";
  if (isToppedResult(result)) return "↑";
  return "✗";
}
