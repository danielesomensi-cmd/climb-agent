import Link from "next/link";

/**
 * A245 B-1 (F2) — offline fallback served by the service worker when a
 * navigation has nothing in cache. Deliberately a static server component with
 * no data fetching: it must render from the precache with zero network.
 */
export default function OfflinePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <span className="text-4xl" aria-hidden="true">
        📡
      </span>
      <h1 className="text-xl font-semibold">You&apos;re offline</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This screen hasn&apos;t been saved for offline use yet. Your training
        plan and today&apos;s session are available without a connection.
      </p>
      <div className="flex flex-col gap-2 pt-2">
        <Link
          href="/today"
          className="flex min-h-[44px] items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground"
        >
          Go to Today
        </Link>
        <Link
          href="/week"
          className="flex min-h-[44px] items-center justify-center rounded-md border px-6 text-sm font-medium"
        >
          Go to Week
        </Link>
      </div>
      <p className="pt-2 text-xs text-muted-foreground">
        Anything you log offline is saved on this device and sent automatically
        when you&apos;re back online.
      </p>
    </div>
  );
}
