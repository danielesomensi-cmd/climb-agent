/**
 * A286 — placeholder per /week, stessa lezione anti-CLS di TodaySkeleton.
 *
 * /week è la pagina più alta dell'app (griglia + 7 day-card) e mostrava uno
 * spinner centrato alto 48px: il salto da vuoto a pieno era il massimo layout
 * shift dell'app. I blocchi qui sotto ricalcano la griglia settimanale e la
 * lista dei giorni, così il contenuto atterra dove stava il placeholder.
 */
export function WeekSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      {/* Griglia 7 giorni */}
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
        {Array.from({ length: 7 }).map((_, i) => (
          <div
            key={i}
            className="h-[70px] animate-pulse rounded-lg border border-border bg-muted/30"
          />
        ))}
      </div>

      {/* Lista giorni */}
      <div className="space-y-3">
        <div className="h-4 w-28 animate-pulse rounded bg-muted/40" />
        {Array.from({ length: 7 }).map((_, i) => (
          <div
            key={i}
            className="space-y-2 rounded-xl border border-border p-4"
          >
            <div className="h-4 w-24 animate-pulse rounded bg-muted/40" />
            <div className="h-16 animate-pulse rounded-md bg-muted/25" />
          </div>
        ))}
      </div>

      <span className="sr-only">Loading your week…</span>
    </div>
  );
}
