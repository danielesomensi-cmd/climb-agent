"use client";

import { ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { OutdoorSession } from "@/lib/types";

/**
 * B410 (B-OUTDOOR-CRAG-PICKER point 3) — which crag of the day to open, or a
 * new one. Shown by Today, Week and /outdoor before the outdoor log form when
 * `needsCragPicker` says so; the form itself never guesses the crag.
 */
export function OutdoorCragPicker({
  sessions,
  onEdit,
  onAdd,
}: {
  sessions: readonly OutdoorSession[];
  onEdit: (session: OutdoorSession) => void;
  onAdd: () => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {sessions.length > 1
          ? `${sessions.length} crags are logged on this day. Which one do you want to open?`
          : "This day already has a session logged. Edit it, or add another crag?"}
      </p>
      <ul className="space-y-2">
        {sessions.map((s) => {
          const n = s.routes?.length ?? 0;
          return (
            <li key={s.spot_name}>
              <Button
                type="button"
                variant="outline"
                className="h-auto min-h-[44px] w-full justify-between gap-3 px-3 py-2 text-left"
                onClick={() => onEdit(s)}
                aria-label={`Edit ${s.spot_name}`}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{s.spot_name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {n} {n === 1 ? "route" : "routes"}
                  </span>
                </span>
                <span className="flex shrink-0 items-center text-xs text-primary">
                  Edit
                  <ChevronRight className="size-4" aria-hidden="true" />
                </span>
              </Button>
            </li>
          );
        })}
      </ul>
      <Button type="button" variant="ghost" className="min-h-[44px] w-full" onClick={onAdd}>
        <Plus className="mr-1 size-4" aria-hidden="true" />
        Add another crag
      </Button>
    </div>
  );
}
