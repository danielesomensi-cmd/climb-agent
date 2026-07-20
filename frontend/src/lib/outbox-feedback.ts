"use client";

import { toast } from "sonner";
import { enqueue } from "@/lib/outbox";

/**
 * A245 B-4 (F4) — shared "queue it, and say so" helper for session feedback.
 *
 * Lives in its own module because /today and /week both submit feedback and a
 * duplicated copy of this would eventually diverge — which is exactly how F4's
 * two identical `catch { /* Non-critical *\/ }` blocks came to exist.
 */
export function queueOrWarn(body: Record<string, unknown>): void {
  const queued = enqueue("feedback", body);
  if (queued) {
    toast("Feedback saved on this device — it will sync when you're back online.", {
      duration: 6000,
    });
  } else {
    // Storage full or unavailable: the one case where we genuinely cannot keep
    // the data. Say so plainly instead of pretending it went through.
    toast.error("Could not save your feedback. Please try again when you have a connection.", {
      duration: 10_000,
    });
  }
}
