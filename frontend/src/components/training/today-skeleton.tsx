/**
 * A245 F-6 (F14) — placeholder that reserves the real page's height.
 *
 * `/today` used to show a single centred spinner and then swap in everything at
 * once. On a slow connection the page jumped from empty to full height in one
 * frame: close to the worst possible CLS, on the app's opening screen.
 *
 * B396 — the blocks follow the page as it is since A286/A308: the day's
 * session first (title, meta line, the 44px Start/Done/Skip row, "Change
 * plan"), then the week progress, the coach entry and the quote — now a text
 * row, no longer the 4:5 photo that made the skeleton ~400px taller than the
 * page it stood in for. It is also the Suspense fallback, so the open goes
 * skeleton → content in one transition instead of spinner → skeleton → content.
 */
export function TodaySkeleton() {
  return (
    <div role="status" data-testid="today-skeleton">
      <div className="space-y-4" aria-hidden="true">
        {/* Day card with today's session */}
        <div className="space-y-3 rounded-xl border border-border px-6 py-4">
          <div className="h-6 w-44 animate-pulse rounded bg-muted/40" />
          <div className="h-3.5 w-56 animate-pulse rounded bg-muted/30" />
          <div className="flex gap-1.5">
            <div className="h-11 w-36 animate-pulse rounded-md bg-muted/40" />
            <div className="h-11 w-20 animate-pulse rounded-md bg-muted/30" />
            <div className="h-11 w-20 animate-pulse rounded-md bg-muted/30" />
          </div>
          <div className="h-11 w-40 animate-pulse rounded-md bg-muted/20" />
        </div>

        {/* Week progress bar */}
        <div className="space-y-1.5">
          <div className="h-4 w-32 animate-pulse rounded bg-muted/30" />
          <div className="h-2 w-full animate-pulse rounded-full bg-muted/40" />
          <div className="h-3.5 w-40 animate-pulse rounded bg-muted/30" />
        </div>

        {/* Coach entry */}
        <div className="h-[74px] animate-pulse rounded-xl border border-border bg-muted/20" />

        {/* Quote — a text row since A308 */}
        <div className="space-y-2 rounded-xl border border-border p-4">
          <div className="h-3.5 w-full animate-pulse rounded bg-muted/30" />
          <div className="h-3.5 w-2/3 animate-pulse rounded bg-muted/30" />
        </div>
      </div>

      {/* Outside the aria-hidden blocks, so screen readers do hear it. */}
      <span className="sr-only">Loading your day…</span>
    </div>
  );
}
