"use client";

/**
 * A-ACTIVATION-TIMING Day 3: empty-state hero on /today.
 *
 * Renders ONE of three pre-session states. Case 1 (session today) is handled
 * by DayCard upstream, not by this component.
 *
 * State matrix:
 *   - pre_start   : today < macrocycle.start_date (fallback fired, plan is future)
 *   - offday      : today has no sessions but the week has a next training day
 *   - empty_week  : today has no sessions AND no next training day this week
 *
 * The "Change start date" affordance is rendered for offday / empty_week only.
 * It is omitted from pre_start because the backend fallback has already made
 * the most conservative start-date choice — offering a change would be noise.
 */

import Link from "next/link";

export type HeroState = "offday" | "empty_week" | "pre_start";

export interface NextSessionInfo {
  date: string;
  weekday: string;
  session_name?: string;
  slot?: string;
  location?: string;
}

interface TodayHeroCTAProps {
  state: HeroState;
  nextSession?: NextSessionInfo;
  startDate?: string;
  startWeekday?: string;
  onPreviewNextSession?: () => void;
  onPreviewFirstSession?: () => void;
  onChangeStartDate?: () => void;
}

const WEEKDAY_FULL = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function weekdayFromISO(iso: string): string {
  const parts = iso.split("-");
  if (parts.length !== 3) return "";
  const d = new Date(
    parseInt(parts[0]),
    parseInt(parts[1]) - 1,
    parseInt(parts[2]),
  );
  return WEEKDAY_FULL[d.getDay()] ?? "";
}

function isTomorrow(iso: string): boolean {
  const parts = iso.split("-");
  if (parts.length !== 3) return false;
  const target = new Date(
    parseInt(parts[0]),
    parseInt(parts[1]) - 1,
    parseInt(parts[2]),
  );
  const tomorrow = new Date();
  tomorrow.setHours(0, 0, 0, 0);
  tomorrow.setDate(tomorrow.getDate() + 1);
  return target.getTime() === tomorrow.getTime();
}

function formatSessionMeta(next: NextSessionInfo): string {
  const parts: string[] = [];
  if (next.session_name) parts.push(next.session_name);
  if (next.slot) parts.push(next.slot);
  if (next.location) parts.push(next.location);
  return parts.join(" · ");
}

export function TodayHeroCTA(props: TodayHeroCTAProps) {
  const {
    state,
    nextSession,
    startDate,
    startWeekday,
    onPreviewNextSession,
    onPreviewFirstSession,
    onChangeStartDate,
  } = props;

  if (state === "pre_start") {
    const day = startWeekday || (startDate ? weekdayFromISO(startDate) : "");
    const tomorrow = startDate ? isTomorrow(startDate) : false;
    const heading = tomorrow
      ? "Your plan starts tomorrow."
      : `Your plan starts ${day}${startDate ? ` ${formatDayMonth(startDate)}` : ""}.`;

    return (
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-6 text-center space-y-4">
        <div className="space-y-2">
          <p className="text-lg font-medium">{heading}</p>
          <p className="text-sm text-muted-foreground">
            Welcome — we&apos;ll see you on {day || "your first training day"}.
          </p>
        </div>

        {nextSession && (
          <div className="rounded-md border bg-background/50 p-3 text-left">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              First session
            </p>
            <p className="mt-1 text-sm font-medium">
              {nextSession.weekday}
              {nextSession.session_name ? ` — ${nextSession.session_name}` : ""}
            </p>
            {(nextSession.slot || nextSession.location) && (
              <p className="text-xs text-muted-foreground">
                {[nextSession.slot, nextSession.location].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        )}

        {onPreviewFirstSession && (
          <button
            type="button"
            onClick={onPreviewFirstSession}
            className="inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Preview first session
          </button>
        )}
      </div>
    );
  }

  if (state === "offday") {
    const meta = nextSession ? formatSessionMeta(nextSession) : "";
    return (
      <div className="rounded-lg border border-dashed p-6 text-center space-y-4">
        <div className="space-y-2">
          <p className="text-lg font-medium">Rest day today</p>
          {/* A235 (P5): rest is framed as productive, never as absence */}
          <p className="text-sm text-muted-foreground">
            Recovery is where the gains happen — your body is consolidating the
            last sessions. Enjoy it.
          </p>
        </div>

        {nextSession && (
          <div className="rounded-md border bg-background/50 p-3 text-left">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Next session
            </p>
            <p className="mt-1 text-sm font-medium">
              {nextSession.weekday}
              {nextSession.session_name ? ` — ${nextSession.session_name}` : ""}
            </p>
            {meta && nextSession.session_name && meta !== nextSession.session_name && (
              <p className="text-xs text-muted-foreground">
                {[nextSession.slot, nextSession.location].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-col items-center gap-2">
          {nextSession && onPreviewNextSession && (
            <button
              type="button"
              onClick={onPreviewNextSession}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Preview session
            </button>
          )}
          {onChangeStartDate ? (
            <button
              type="button"
              onClick={onChangeStartDate}
              className="text-xs text-muted-foreground underline hover:text-foreground"
            >
              Change start date
            </button>
          ) : (
            <Link
              href="/onboarding/start-week"
              className="text-xs text-muted-foreground underline hover:text-foreground"
            >
              Change start date
            </Link>
          )}
        </div>
      </div>
    );
  }

  // empty_week
  return (
    <div className="rounded-lg border border-dashed p-6 text-center space-y-4">
      <div className="space-y-2">
        <p className="text-lg font-medium">No sessions planned this week</p>
        <p className="text-sm text-muted-foreground">
          Your availability may be too tight for the current phase. Adjust your
          availability or shift your start date to get back on track.
        </p>
      </div>

      <div className="flex flex-col items-center gap-2">
        <Link
          href="/settings"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Review availability
        </Link>
        {onChangeStartDate ? (
          <button
            type="button"
            onClick={onChangeStartDate}
            className="text-xs text-muted-foreground underline hover:text-foreground"
          >
            Change start date
          </button>
        ) : (
          <Link
            href="/onboarding/start-week"
            className="text-xs text-muted-foreground underline hover:text-foreground"
          >
            Change start date
          </Link>
        )}
      </div>
    </div>
  );
}

const MONTH_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatDayMonth(iso: string): string {
  const parts = iso.split("-");
  if (parts.length !== 3) return "";
  const d = new Date(
    parseInt(parts[0]),
    parseInt(parts[1]) - 1,
    parseInt(parts[2]),
  );
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}
