"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { WeekPlan } from "@/lib/types";
import { formatDateShort } from "@/lib/format";

interface MoveSessionDialogProps {
  open: boolean;
  sessionId: string;
  fromDate: string;
  fromSlot: string;
  weekPlan: WeekPlan;
  onClose: () => void;
  onApply: (data: { to_date: string; to_slot: string }) => void;
}

const SLOTS = ["morning", "lunch", "evening"];

const SLOT_LABELS: Record<string, string> = {
  morning: "Morning",
  lunch: "Lunch",
  evening: "Evening",
};

const WEEKDAY_LABELS: Record<string, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};

/**
 * The slots a session can be moved onto. A slot is free only when it holds no
 * session at all: a done or skipped session still occupies it — since A301 the
 * backend refuses a move onto it with a 422 (past sessions are immutable).
 */
export function freeMoveSlots(
  weekPlan: WeekPlan,
  fromDate: string,
  fromSlot: string,
): { date: string; weekday: string; slot: string }[] {
  return (weekPlan.weeks[0]?.days ?? [])
    .flatMap((day) =>
      SLOTS.filter((slot) => !(day.sessions ?? []).some((s) => s.slot === slot)).map((slot) => ({
        date: day.date,
        weekday: day.weekday,
        slot,
      })),
    )
    .filter((s) => !(s.date === fromDate && s.slot === fromSlot));
}

export function MoveSessionDialog({
  open,
  // B355 — `sessionId` resta nella props interface (i due chiamanti la passano e
  // identifica la sessione da spostare) ma il dialog non la usa: sceglie solo la
  // destinazione e la restituisce a onApply.
  fromDate,
  fromSlot,
  weekPlan,
  onClose,
  onApply,
}: MoveSessionDialogProps) {
  const [selected, setSelected] = useState<{ date: string; slot: string } | null>(null);

  const freeSlots = freeMoveSlots(weekPlan, fromDate, fromSlot);

  // Group by day
  const grouped = new Map<string, typeof freeSlots>();
  for (const s of freeSlots) {
    const key = s.date;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(s);
  }

  const handleApply = () => {
    if (!selected) return;
    onApply({ to_date: selected.date, to_slot: selected.slot });
    setSelected(null);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) {
          setSelected(null);
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Move session</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Select a free slot to move this session to.
          </p>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {freeSlots.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">
              No free slots available this week.
            </p>
          ) : (
            Array.from(grouped.entries()).map(([date, slots]) => {
              const weekday = slots[0]?.weekday ?? "";
              const dayLabel = WEEKDAY_LABELS[weekday.toLowerCase()] ?? weekday;
              return (
                <div key={date} className="space-y-1">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {dayLabel} — {formatDateShort(date)}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {slots.map((s) => {
                      const isSelected =
                        selected?.date === s.date && selected?.slot === s.slot;
                      return (
                        <button
                          key={`${s.date}-${s.slot}`}
                          type="button"
                          className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                            isSelected
                              ? "border-primary bg-primary/10 text-primary font-medium"
                              : "border-muted text-muted-foreground hover:border-primary/40"
                          }`}
                          onClick={() => setSelected({ date: s.date, slot: s.slot })}
                        >
                          {SLOT_LABELS[s.slot] ?? s.slot}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleApply}
            disabled={!selected}
          >
            Move here
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
