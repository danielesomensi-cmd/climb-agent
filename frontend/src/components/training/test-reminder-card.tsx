"use client";

import { useState } from "react";
import { Gauge } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { respondToTestReminder } from "@/lib/api";
import type { TestReminder, TestReminderOption } from "@/lib/types";

/**
 * A246 — the periodic retest reminder, finally on screen.
 *
 * The backend has emitted this every ~6 weeks since it was written
 * (`should_show_test_reminder`, planner_v2) and a whole endpoint existed to
 * answer it — but no component ever read the payload, so no user has ever seen
 * it (A245 G-4 / finding F52). The consequence was not cosmetic: periodic
 * recalibration is what keeps prescriptions tied to current strength, so every
 * plan has been running on baselines that only ever got older.
 *
 * Deliberately NOT dismissible with an ✕: the three options ARE the dismissal,
 * and each one tells the engine something different. A silent dismiss would put
 * us back where we started — a reminder that never leads to a decision.
 */
const OPTION_LABEL: Record<TestReminderOption, string> = {
  confirm: "Schedule test week",
  postpone_1_week: "Next week",
  skip_cycle: "Not this cycle",
};

/** What the user is actually choosing, in their terms. */
const OPTION_HINT: Record<TestReminderOption, string> = {
  confirm: "Adds a test session to next week's plan",
  postpone_1_week: "Ask me again in 7 days",
  skip_cycle: "Ask me again in about 6 weeks",
};

const OPTION_DONE: Record<TestReminderOption, string> = {
  confirm: "Test week scheduled — you'll find it in next week's plan.",
  postpone_1_week: "OK, we'll ask again next week.",
  skip_cycle: "OK, we'll ask again in about 6 weeks.",
};

export function TestReminderCard({
  reminder,
  onResponded,
}: {
  reminder: TestReminder;
  onResponded: () => void;
}) {
  const [pending, setPending] = useState<TestReminderOption | null>(null);
  const [answered, setAnswered] = useState(false);

  if (answered) return null;

  async function choose(option: TestReminderOption) {
    if (pending) return;
    setPending(option);
    try {
      await respondToTestReminder(option);
      setAnswered(true);
      toast.success(OPTION_DONE[option]);
      // The reminder lives on the week payload, and `confirm` also changes next
      // week's plan — refetch rather than hiding it locally and drifting.
      onResponded();
    } catch (err) {
      // Never pretend it landed: the whole point of this card is that a
      // decision reaches the engine.
      toast.error(
        err instanceof Error && err.message
          ? err.message
          : "Couldn't save your choice. Please try again.",
      );
      setPending(null);
    }
  }

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardContent className="space-y-3 px-4 py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
            <Gauge className="h-5 w-5 text-primary" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold">Time to retest</p>
            <p className="text-sm text-muted-foreground">{reminder.message}</p>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          {reminder.options.map((option) => (
            <Button
              key={option}
              variant={option === "confirm" ? "default" : "outline"}
              disabled={pending !== null}
              // Stacked, not side by side: at 390px the label and the hint
              // together overflow the button and the hint gets clipped.
              className="h-auto min-h-[44px] w-full flex-col items-start gap-0.5 py-2.5 text-left whitespace-normal"
              onClick={() => choose(option)}
            >
              <span className="font-medium">
                {pending === option ? "Saving..." : OPTION_LABEL[option]}
              </span>
              <span className="text-xs font-normal opacity-70">{OPTION_HINT[option]}</span>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
