// A315 — automatic re-schedule of a key session lost by the user's action.
// The server applies the validated A294 proposal right after the skip /
// removal / override and reports it in `auto_reschedules`; the client says so
// in a toast with an Undo (`undo_auto_reschedule`).
import { toast } from "sonner";
import { keyLabel, shortDay } from "@/lib/key-sessions";

export type AutoReschedule = {
  adaptation_id: string;
  keys: string[];
  date: string;
  slot: string;
  session_id: string;
  session_name?: string | null;
  replaced?: { date: string; slot: string; session_id: string; session_name?: string | null } | null;
};

/** Title + description of the toast for one automatic re-schedule. */
export function autoRescheduleText(a: AutoReschedule): { title: string; description: string } {
  const keys = a.keys.filter((k) => k !== "try_hard").map(keyLabel).join(" + ") || "Key session";
  const where = `${shortDay(a.date)} ${a.slot}`;
  const what = a.session_name || a.session_id;
  const description = a.replaced
    ? `${what} on ${where}, in place of ${a.replaced.session_name || a.replaced.session_id}.`
    : `${what} on ${where}.`;
  return { title: `${keys} moved to ${shortDay(a.date)}`, description };
}

/** The undo event of one automatic re-schedule. */
export function undoAutoRescheduleEvent(a: AutoReschedule): Record<string, unknown> {
  return { event_type: "undo_auto_reschedule", adaptation_id: a.adaptation_id };
}

/**
 * One toast per automatic re-schedule, with an Undo that sends
 * `undo_auto_reschedule` through *runEvents* (the serialized week-events
 * queue, so the undo starts from the latest plan).
 */
export function showAutoReschedules(
  list: AutoReschedule[] | null | undefined,
  runEvents: (events: Array<Record<string, unknown>>) => Promise<unknown>,
): void {
  for (const a of list ?? []) {
    const { title, description } = autoRescheduleText(a);
    toast(title, {
      description,
      duration: 15000,
      action: {
        label: "Undo",
        onClick: () => {
          runEvents([undoAutoRescheduleEvent(a)])
            .then(() => toast("Re-schedule undone"))
            .catch((e: unknown) =>
              toast.error(e instanceof Error ? e.message : "Could not undo the re-schedule"),
            );
        },
      },
    });
  }
}
