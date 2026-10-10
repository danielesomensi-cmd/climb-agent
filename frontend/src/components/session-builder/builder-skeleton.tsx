/**
 * A309 — placeholder for the session builder's async states (editor, preview,
 * picker, Suspense fallbacks), in place of a bare "Loading..." line that made
 * the screen flash empty and then jump. Same pulse blocks as TodaySkeleton.
 */
export function BuilderSkeleton({ rows = 4, withInput = true }: { rows?: number; withInput?: boolean }) {
  return (
    <div role="status" className="space-y-3 py-2">
      {withInput && <div aria-hidden="true" className="h-9 animate-pulse rounded-md bg-muted/40" />}
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} aria-hidden="true" className="h-14 animate-pulse rounded-lg bg-muted/30" />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}
