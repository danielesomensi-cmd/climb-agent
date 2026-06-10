"use client";

import { useRouter } from "next/navigation";
import { useSubscription } from "@/lib/hooks/use-subscription";

export function TrialBanner() {
  const { status, isActive, isTrialing, trialDaysRemaining, loading } =
    useSubscription();
  const router = useRouter();

  if (loading) return null;

  // Active paid subscriber — no banner
  if (isActive && !isTrialing) return null;

  // B258: never-started subscribers (checkout begun but not completed, or no
  // row at all) get a clear "start" CTA — never the "trial has ended" copy,
  // which only applies to someone who actually had a trial. Without this the
  // user lands in a dead-end: the app looks normal but every training action
  // 402s with no path to subscribe. Mirrors backend _NEVER_STARTED_STATUSES.
  if (status === "pending_checkout" || status === "none") {
    return (
      <div className="flex items-center justify-between bg-primary/5 text-foreground border-b border-border px-4 py-2 text-sm">
        <span>Complete your subscription to start training.</span>
        <button
          onClick={() => router.push("/subscribe")}
          className="text-xs font-medium underline underline-offset-2 text-primary"
        >
          Subscribe
        </button>
      </div>
    );
  }

  // Trialing — show countdown
  if (isTrialing) {
    const days = trialDaysRemaining ?? 0;
    const isUrgent = days <= 3;
    return (
      <div
        className={`flex items-center justify-between px-4 py-2 text-sm ${
          isUrgent
            ? "bg-warning/10 text-warning border-b border-warning/20"
            : "bg-primary/5 text-muted-foreground border-b border-border"
        }`}
      >
        <span>
          {days === 0
            ? "Trial ends today"
            : days === 1
              ? "1 day left in your free trial"
              : `${days} days left in your free trial`}
        </span>
        <button
          onClick={() => router.push("/subscribe")}
          className={`text-xs font-medium underline underline-offset-2 ${
            isUrgent ? "text-warning" : "text-primary"
          }`}
        >
          Subscribe
        </button>
      </div>
    );
  }

  // Expired (past_due, canceled, expired) — show CTA
  return (
    <div className="flex items-center justify-between bg-destructive/10 text-destructive border-b border-destructive/20 px-4 py-2 text-sm">
      <span>Your trial has ended. Subscribe to continue training.</span>
      <button
        onClick={() => router.push("/subscribe")}
        className="text-xs font-medium underline underline-offset-2 text-destructive"
      >
        Subscribe
      </button>
    </div>
  );
}
