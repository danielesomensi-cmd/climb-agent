"use client";

import { useState } from "react";
import { Calendar, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { WeeklyCheckinSheet } from "./weekly-checkin-sheet";

/**
 * Returns the next Monday (YYYY-MM-DD) from a given date.
 * If today IS Monday, returns the following Monday.
 */
function getNextMonday(from: Date = new Date()): string {
  const d = new Date(from);
  const day = d.getDay(); // 0=Sun, 1=Mon...
  const daysUntilMonday = day === 0 ? 1 : day === 1 ? 7 : 8 - day;
  d.setDate(d.getDate() + daysUntilMonday);
  return d.toISOString().split("T")[0];
}

/**
 * Determines whether to show the weekly check-in prompt.
 * - Sunday (day 0): always show
 * - Monday (day 1) before noon: grace period (show if not dismissed this week)
 * - Otherwise: don't show
 */
function shouldShowCheckin(): boolean {
  const now = new Date();
  const day = now.getDay();
  if (day === 0) return true; // Sunday
  if (day === 1 && now.getHours() < 12) return true; // Monday morning grace
  return false;
}

interface Props {
  onPlanUpdated: () => void;
}

export function WeeklyCheckinCard({ onPlanUpdated }: Props) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Check dismiss flag in sessionStorage (survives page refreshes within session)
  const dismissKey = `checkin_dismissed_${getNextMonday()}`;

  if (!shouldShowCheckin()) return null;
  if (dismissed) return null;

  // Check sessionStorage
  if (typeof window !== "undefined" && sessionStorage.getItem(dismissKey)) {
    return null;
  }

  function handleDismiss() {
    setDismissed(true);
    if (typeof window !== "undefined") {
      sessionStorage.setItem(dismissKey, "1");
    }
  }

  return (
    <>
      <Card
        className="border-primary/30 bg-primary/5 cursor-pointer hover:bg-primary/10 transition-colors"
        onClick={() => setSheetOpen(true)}
      >
        <CardContent className="flex items-center gap-3 py-4 px-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <Calendar className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold">Plan your week</p>
            <p className="text-xs text-muted-foreground">
              Review next week&apos;s schedule and adjust if needed
            </p>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </CardContent>
      </Card>

      <WeeklyCheckinSheet
        open={sheetOpen}
        nextWeekStart={getNextMonday()}
        onClose={() => {
          setSheetOpen(false);
          handleDismiss();
        }}
        onPlanUpdated={onPlanUpdated}
      />
    </>
  );
}
