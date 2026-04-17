"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useCustomSessions } from "@/lib/hooks/queries";
import { Dumbbell, Plus, Pencil, Play, ChevronDown } from "lucide-react";

interface MySessionsSectionProps {
  enabled?: boolean;
}

export function MySessionsSection({ enabled = true }: MySessionsSectionProps) {
  const router = useRouter();
  const { data, isLoading } = useCustomSessions(enabled);
  const sessions = data?.sessions ?? [];
  const [expanded, setExpanded] = useState(false);

  const count = sessions.length;

  return (
    <>
      {/* Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">My Sessions</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* Collapsible card */}
      <div className="rounded-xl border bg-gradient-to-r from-violet-500/20 to-violet-600/5 border-violet-500/30 overflow-hidden">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center gap-4 p-4 text-left transition-all active:scale-[0.99]"
          aria-expanded={expanded}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/20 text-violet-400">
            <Dumbbell className="size-6" />
          </div>
          <div className="flex-1">
            <div className="font-semibold">My Sessions</div>
            <div className="text-xs text-muted-foreground">
              {isLoading ? "Loading..." : count === 0 ? "No sessions yet" : `${count} saved session${count !== 1 ? "s" : ""}`}
            </div>
          </div>
          <ChevronDown
            className={`size-5 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </button>

        {expanded && (
          <div className="flex flex-col gap-2 border-t border-violet-500/20 bg-black/10 p-3">
            {/* Existing sessions */}
            {sessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center gap-3 rounded-lg border border-violet-500/20 bg-background/50 p-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{session.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {session.exercise_count} exercises · Load {session.estimated_load_score} · ~{session.estimated_duration_minutes} min
                  </p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9"
                    onClick={(e) => { e.stopPropagation(); router.push(`/session-builder/${session.id}/view`); }}
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9"
                    onClick={(e) => { e.stopPropagation(); router.push(`/session-builder/${session.id}`); }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}

            {/* Build a Session button */}
            <button
              onClick={() => router.push("/session-builder")}
              className="flex items-center gap-3 rounded-lg border border-dashed border-violet-500/30 p-3 text-left transition-all hover:bg-violet-500/5 active:scale-[0.99]"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/10 text-violet-400 shrink-0">
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
    </>
  );
}
