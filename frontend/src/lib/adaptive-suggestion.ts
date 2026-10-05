/**
 * B369 / A301 — the adaptive suggestion returned by POST /api/feedback.
 *
 * After a very_hard or failed session the backend used to rewrite the plan on
 * its own (downgrade the next hard session, insert a recovery day). Since B369
 * it changes nothing and returns `adaptive_suggestion` instead: "consider
 * lightening your next hard session". Daniele's decision (2026-10-05): "non
 * facciamo cose automatiche, se è very hard ti chiedo io di declassare con una
 * custom". So the UI only shows the text — one toast per feedback submit, from
 * every path (dialog, guided, custom player, offline outbox), with a shortcut
 * to the session builder. Nothing is changed automatically.
 */
import { toast } from "sonner";
import type { AdaptiveSuggestion } from "./types";

export const SESSION_BUILDER_HREF = "/session-builder";

function isSuggestion(value: unknown): value is AdaptiveSuggestion {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { message?: unknown }).message === "string" &&
    ((value as { message: string }).message.trim().length > 0)
  );
}

/** Title + description of the toast, or null when there is nothing to say. */
export function describeAdaptiveSuggestion(raw: unknown): { title: string; description: string } | null {
  if (!isSuggestion(raw)) return null;
  const title = raw.kind === "recovery_day" ? "Consider a recovery day" : "Consider lightening the next hard session";
  let description = raw.message.trim();
  // The server already says it; make sure the UI never implies a change.
  if (!/nothing was changed/i.test(description)) description += " Nothing was changed in your plan.";
  return { title, description };
}

/** Show the toast for a /api/feedback response (no-op when nothing is suggested). */
export function notifyAdaptiveSuggestion(raw: unknown): void {
  const msg = describeAdaptiveSuggestion(raw);
  if (!msg) return;
  toast(msg.title, {
    description: msg.description,
    duration: 15000,
    action: {
      label: "Build a custom",
      onClick: () => {
        if (typeof window !== "undefined") window.location.assign(SESSION_BUILDER_HREF);
      },
    },
  });
}
