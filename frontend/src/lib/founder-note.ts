/**
 * A264 — visibility rule for the founder note shown on /today.
 *
 * Kept out of the component (and out of JSX) for the same reason B304 pulled
 * the tooltip geometry into `radarTooltip.ts`: the repo has no component
 * renderer in its test setup, so anything only expressible as JSX is
 * effectively untested. The rule is small but it decides whether a hand-written
 * message reaches a real person — worth pinning down.
 */

export interface FounderNoteData {
  id: string;
  title: string;
  body: string[];
  cta_label?: string;
  cta_href?: string;
  signature?: string;
  dismissed_at?: string | null;
}

/**
 * Show the note only when there is one, it has not been dismissed, it has
 * something to say, and the user is looking at today.
 *
 * `locallyDismissed` covers the optimistic hide: the card disappears on tap
 * without waiting for the PUT, and a failed PUT must not make it reappear
 * mid-session.
 */
export function shouldShowFounderNote(
  note: FounderNoteData | null | undefined,
  opts: { isViewingToday: boolean; locallyDismissed?: boolean },
): boolean {
  if (!note) return false;
  if (!opts.isViewingToday) return false;
  if (opts.locallyDismissed) return false;
  if (note.dismissed_at) return false;
  // An empty note is a data error, not a blank card.
  if (!note.title?.trim()) return false;
  if (!note.body?.some((p) => p?.trim())) return false;
  return true;
}

/** A CTA renders only when both halves are present. */
export function founderNoteCta(
  note: FounderNoteData,
): { label: string; href: string } | null {
  if (!note.cta_label?.trim() || !note.cta_href?.trim()) return null;
  return { label: note.cta_label, href: note.cta_href };
}
