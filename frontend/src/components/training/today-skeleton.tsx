/**
 * A245 F-6 (F14) — placeholder that reserves the real page's height.
 *
 * `/today` used to show a single centred spinner and then swap in everything at
 * once — progress bar, weather card, day card, hero quote. On a slow connection
 * the page jumped from empty to full height in one frame: close to the worst
 * possible CLS, on the app's opening screen.
 *
 * The blocks below mirror the real layout's vertical rhythm, so the content
 * lands where the skeleton already was.
 */
export function TodaySkeleton() {
  return (
    <div className="space-y-4 py-2" aria-hidden="true">
      {/* Week progress bar */}
      <div className="h-14 animate-pulse rounded-lg bg-muted/40" />

      {/* Day card — the tallest block, so it carries most of the reserved height */}
      <div className="space-y-3 rounded-lg border border-border p-4">
        <div className="h-5 w-32 animate-pulse rounded bg-muted/40" />
        <div className="h-24 animate-pulse rounded-md bg-muted/30" />
        <div className="h-24 animate-pulse rounded-md bg-muted/30" />
      </div>

      {/* Quote card — fixed 4/5 aspect in the real layout */}
      <div className="aspect-[4/5] w-full animate-pulse rounded-lg bg-muted/20" />

      <span className="sr-only">Loading your day…</span>
    </div>
  );
}
