"use client";

/**
 * A-ACTIVATION-TIMING Day 3: visual regression harness for /today empty states.
 *
 * Renders all 4 pre-session states side-by-side with synthetic props. Used
 * to eyeball-test the hero without needing 4 real user accounts.
 *
 * Access control:
 *   - Accessible in local dev (npm run dev) and on Vercel preview branches.
 *   - Blocked on the production domains (climbagent.app + legacy vercel.app URL).
 *
 * Note: Vercel preview builds run with NODE_ENV="production" (same as prod),
 * so a pure NODE_ENV check would hide the page on previews — exactly where
 * we need it for Day 4 testing. The hostname check below keeps preview URLs
 * functional while blocking the production domain. If you want to gate more
 * strictly, add a server-side redirect in middleware.
 */

import { useEffect, useState } from "react";
import { TodayHeroCTA } from "@/components/training/today-hero-cta";

const PROD_HOSTNAMES = [
  "climbagent.app",
  "www.climbagent.app",
  "climb-agent.vercel.app",
];

function isoDaysFromToday(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function weekdayOfOffset(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][
    d.getDay()
  ];
}

export default function DevTodayStatesPage() {
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // Local dev is always allowed; Vercel preview is allowed; prod domain is blocked.
    if (process.env.NODE_ENV !== "production") {
      setAllowed(true);
      return;
    }
    setAllowed(!PROD_HOSTNAMES.includes(window.location.hostname));
  }, []);

  if (allowed === null) return null;
  if (!allowed) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <p className="text-muted-foreground">Not available.</p>
      </div>
    );
  }

  const tomorrowISO = isoDaysFromToday(1);
  const tomorrowWeekday = weekdayOfOffset(1);
  const nextWeekISO = isoDaysFromToday(5);
  const nextWeekWeekday = weekdayOfOffset(5);

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <header className="space-y-2 border-b pb-4">
        <h1 className="text-2xl font-semibold">/today empty-state harness</h1>
        <p className="text-sm text-muted-foreground">
          A-ACTIVATION-TIMING Day 3 — all 4 pre-session states rendered with
          synthetic props. Compare against live /today behaviour before merge.
        </p>
      </header>

      {/* Case 1 — session today (rendered by DayCard, stubbed here) */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Case 1 — session today
        </h2>
        <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-sm text-muted-foreground">
          Handled by{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">DayCard</code>{" "}
          on /today — not part of the hero component. Visual reference lives on
          the real page with a planned session for today.
        </div>
      </section>

      {/* Case 2 — offday */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Case 2 — offday (next session this week)
        </h2>
        <TodayHeroCTA
          state="offday"
          nextSession={{
            date: tomorrowISO,
            weekday: tomorrowWeekday,
            session_name: "Strength Long",
            slot: "evening",
            location: "gym",
          }}
          onPreviewNextSession={() => alert(`Would navigate to /today?date=${tomorrowISO}`)}
          onChangeStartDate={() => alert("Would navigate to /onboarding/start-week")}
        />
      </section>

      {/* Case 3 — empty_week */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Case 3 — empty_week (no training days this week)
        </h2>
        <TodayHeroCTA
          state="empty_week"
          onChangeStartDate={() => alert("Would navigate to /onboarding/start-week")}
        />
      </section>

      {/* Case 4 — pre_start (today < macrocycle.start_date) */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Case 4 — pre_start (plan starts in the future)
        </h2>
        <TodayHeroCTA
          state="pre_start"
          startDate={nextWeekISO}
          nextSession={{
            date: nextWeekISO,
            weekday: nextWeekWeekday,
            session_name: "Power Contact",
            slot: "morning",
            location: "gym",
          }}
          onPreviewFirstSession={() =>
            alert(`Would navigate to /week?date=${nextWeekISO}`)
          }
        />
      </section>

      {/* Edge: pre_start with startDate = tomorrow */}
      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Case 4b — pre_start (starts tomorrow, copy variant)
        </h2>
        <TodayHeroCTA
          state="pre_start"
          startDate={tomorrowISO}
          nextSession={{
            date: tomorrowISO,
            weekday: tomorrowWeekday,
            session_name: "Endurance Moderate",
            slot: "evening",
            location: "home",
          }}
          onPreviewFirstSession={() =>
            alert(`Would navigate to /week?date=${tomorrowISO}`)
          }
        />
      </section>
    </main>
  );
}
