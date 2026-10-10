"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { KeyConflictDialog } from "@/components/training/key-conflict-dialog";
import { useCustomSessions } from "@/lib/hooks/queries";
import { useStartCustomSession } from "./start-custom-session";
import { Dumbbell, Plus, Play, ChevronDown, Loader2 } from "lucide-react";

interface MySessionsSectionProps {
  enabled?: boolean;
}

/** A309: rows shown before "Show all (n)" — keeps /free-session scannable. */
const VISIBLE_SESSIONS = 3;

export function MySessionsSection({ enabled = true }: MySessionsSectionProps) {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useCustomSessions(enabled);
  const sessions = data?.sessions ?? [];
  const { start, startingId, keyDialogProps } = useStartCustomSession();
  // null = the user has not toggled yet: open by default when there is
  // something to play (a daily user should not tap twice to reach it).
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const [showAll, setShowAll] = useState(false);

  const count = sessions.length;
  const isExpanded = expanded ?? count > 0;
  const visible = showAll ? sessions : sessions.slice(0, VISIBLE_SESSIONS);

  const summary = isLoading
    ? "Loading…"
    : isError
      ? "Couldn't load your sessions"
      : count === 0
        ? "No sessions yet"
        : `${count} saved session${count !== 1 ? "s" : ""}`;

  return (
    <>
      {/* Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">My Sessions</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* Collapsible card */}
      <div className="rounded-xl border bg-gradient-to-r from-brand/20 to-brand/5 border-brand/30 overflow-hidden">
        <button
          type="button"
          onClick={() => setExpanded(!isExpanded)}
          className="flex w-full items-center gap-4 p-4 text-left transition-all active:scale-[0.99]"
          aria-expanded={isExpanded}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-muted text-brand">
            <Dumbbell className="size-6" />
          </div>
          <div className="flex-1">
            <div className="font-semibold">{summary}</div>
            <div className="text-xs text-muted-foreground">Your own sessions, built from the catalog</div>
          </div>
          <ChevronDown
            className={`size-5 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""}`}
          />
        </button>

        {isExpanded && (
          <div className="flex flex-col gap-2 border-t border-brand/20 bg-card p-3">
            {isError && (
              <div className="flex items-center justify-between gap-2 px-1">
                <p className="text-sm text-danger">Couldn&apos;t load your sessions</p>
                <Button variant="ghost" className="h-11" onClick={() => void refetch()}>
                  Retry
                </Button>
              </div>
            )}

            {/* Existing sessions: the row opens the preview, Start plays it */}
            {visible.map((session) => {
              const starting = startingId === session.id;
              return (
                <div
                  key={session.id}
                  className="flex items-center gap-2 rounded-lg border border-border bg-card"
                >
                  <button
                    type="button"
                    onClick={() => router.push(`/session-builder/${session.id}/view`)}
                    className="flex min-h-14 min-w-0 flex-1 flex-col justify-center rounded-lg p-3 text-left transition-colors hover:bg-accent active:scale-[0.99]"
                  >
                    <span className="text-sm font-semibold truncate">{session.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {session.exercise_count} exercises · Load {session.estimated_load_score} · ~{session.estimated_duration_minutes} min
                    </span>
                  </button>
                  <Button
                    className="mr-2 h-11 px-4"
                    disabled={startingId !== null}
                    onClick={() => void start(session.id)}
                    aria-label={`Start ${session.name}`}
                  >
                    {starting ? <Loader2 className="animate-spin" /> : <Play />}
                    Start
                  </Button>
                </div>
              );
            })}

            {count > VISIBLE_SESSIONS && (
              <Button variant="ghost" className="h-11" onClick={() => setShowAll((v) => !v)}>
                {showAll ? "Show fewer" : `Show all (${count})`}
              </Button>
            )}

            {/* Build a Session button */}
            <button
              type="button"
              onClick={() => router.push("/session-builder")}
              className="flex items-center gap-3 rounded-lg border border-dashed border-brand/30 p-3 text-left transition-all hover:bg-brand/10 active:scale-[0.99]"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand/15 text-brand shrink-0">
                <Plus className="size-5" />
              </div>
              <div>
                <div className="text-sm font-semibold">Build a Session</div>
                <div className="text-xs text-muted-foreground">Create from the exercise catalog</div>
              </div>
            </button>
          </div>
        )}
      </div>

      <KeyConflictDialog {...keyDialogProps} />
    </>
  );
}
