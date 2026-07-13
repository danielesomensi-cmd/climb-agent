"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { createBillingPortal } from "@/lib/api";

export function TrialBanner() {
  const { status, isActive, isTrialing, trialDaysRemaining, hasPaymentMethod, loading } =
    useSubscription();
  const router = useRouter();
  const [portalLoading, setPortalLoading] = useState(false);

  // A232: trialing users without a card add one via the Billing Portal —
  // /subscribe would bounce them back to /today (B212 already_active guard).
  async function openPortal() {
    if (portalLoading) return;
    setPortalLoading(true);
    try {
      const { portal_url } = await createBillingPortal();
      window.location.href = portal_url;
    } catch {
      // Portal unavailable (no customer yet, or misconfig) — fall back to
      // settings, where the subscription section offers the same path.
      setPortalLoading(false);
      router.push("/settings");
    }
  }

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

  // Trialing — show countdown; without a card on file, the CTA adds one
  // before the trial cancels itself (A232 missing_payment_method: cancel).
  if (isTrialing) {
    const days = trialDaysRemaining ?? 0;
    const isUrgent = days <= 3;
    const countdown =
      days === 0
        ? "Trial ends today"
        : days === 1
          ? "1 day left in your free trial"
          : `${days} days left in your free trial`;
    return (
      <div
        className={`flex items-center justify-between px-4 py-2 text-sm ${
          isUrgent
            ? "bg-warning/10 text-warning border-b border-warning/20"
            : "bg-primary/5 text-muted-foreground border-b border-border"
        }`}
      >
        <span>
          {hasPaymentMethod ? countdown : `${countdown} — no card on file`}
        </span>
        {!hasPaymentMethod && (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className={`text-xs font-medium underline underline-offset-2 disabled:opacity-50 ${
              isUrgent ? "text-warning" : "text-primary"
            }`}
          >
            {portalLoading ? "Opening…" : "Add payment method"}
          </button>
        )}
      </div>
    );
  }

  // Expired (past_due, canceled, expired) — show CTA
  return (
    <div className="flex items-center justify-between bg-destructive/10 text-destructive border-b border-destructive/20 px-4 py-2 text-sm">
      <span>
        Your trial has ended — subscribe to continue. Your training data is
        safe.
      </span>
      <button
        onClick={() => router.push("/subscribe")}
        className="text-xs font-medium underline underline-offset-2 text-destructive"
      >
        Subscribe
      </button>
    </div>
  );
}
