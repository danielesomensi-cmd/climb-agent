/**
 * A295 review — limitation suggestions returned by POST /api/feedback.
 *
 * The server already computes them (B38: a hard rating on an exercise whose
 * zone is under "monitor"; A295: pain 3/3 on a zone that is not a limitation
 * yet), but until now no screen showed them. One toast per feedback submit,
 * with a shortcut to the limitations section of Settings. Nothing is changed
 * automatically: the athlete decides.
 */
import { toast } from "sonner";

export interface LimitationSuggestion {
  exercise_id?: string | null;
  zone: string;
  current_severity?: string;
  suggested_severity?: string;
  reason?: string;
  source?: string;
}

export const LIMITATIONS_SETTINGS_HREF = "/settings#sec-limitations";

function isSuggestion(value: unknown): value is LimitationSuggestion {
  return typeof value === "object" && value !== null && typeof (value as { zone?: unknown }).zone === "string";
}

/** Title + description of the toast, or null when there is nothing to say. */
export function describeLimitationSuggestions(raw: unknown): { title: string; description: string } | null {
  if (!Array.isArray(raw)) return null;
  const items = raw.filter(isSuggestion);
  if (items.length === 0) return null;
  const zones = Array.from(new Set(items.map((s) => s.zone)));
  const fromPain = items.some((s) => s.source === "pain");
  const title = fromPain
    ? `Pain reported on your ${zones.join(", ")}`
    : `Your ${zones.join(", ")} may need more care`;
  const description = fromPain
    ? "Consider marking it as a limitation: the plan then avoids the exercises that load it. Nothing changes until you decide."
    : "That was hard on a zone you are monitoring. Consider raising it to an active limitation.";
  return { title, description };
}

/** Show the toast for a /api/feedback response (no-op when nothing is suggested). */
export function notifyLimitationSuggestions(raw: unknown): void {
  const msg = describeLimitationSuggestions(raw);
  if (!msg) return;
  toast(msg.title, {
    description: msg.description,
    duration: 15000,
    action: {
      label: "Review",
      onClick: () => {
        if (typeof window !== "undefined") window.location.assign(LIMITATIONS_SETTINGS_HREF);
      },
    },
  });
}
