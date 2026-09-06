"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { toast } from "sonner";
import { TopBar } from "@/components/layout/top-bar";
import { PaywallHero } from "@/components/paywall/PaywallHero";
import { ValueBullets } from "@/components/paywall/ValueBullets";
import { TierCard } from "@/components/paywall/TierCard";
import { PaywallFAQ } from "@/components/paywall/PaywallFAQ";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { createCheckoutSession } from "@/lib/api";
import { captureUtmOnMount, trackEvent } from "@/lib/analytics";
import { foundingBadgeCopy } from "@/config/founding";

const PRICE_ID_FOUNDER = process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_FOUNDER ?? "";
const PRICE_ID_STANDARD =
  process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_STANDARD ?? "";

export function SubscribeContent() {
  const { user } = useUser();
  const searchParams = useSearchParams();
  const isPreview = searchParams?.get("preview") === "1";
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A285 — `enforced` defaults to true (and stays true while loading), so the
  // notice appears only on an explicit server "billing is paused".
  const { enforced, loading: subLoading } = useSubscription();
  const billingPaused = !subLoading && !enforced;

  const tiersRef = useRef<HTMLDivElement>(null);
  const scrolledEventFired = useRef(false);

  // Analytics — page view + UTM capture
  useEffect(() => {
    captureUtmOnMount();
    trackEvent("subscribe_viewed", isPreview ? { preview: true } : undefined);
  }, [isPreview]);

  // Persistent preview-mode toast
  useEffect(() => {
    if (!isPreview) return;
    toast.info("Preview mode — checkout disabled", {
      duration: Infinity,
      id: "paywall-preview-mode",
    });
    return () => {
      toast.dismiss("paywall-preview-mode");
    };
  }, [isPreview]);

  // `paywall_scrolled_to_tiers` — fires once when the TierCard block
  // enters the viewport (>=30% visible).
  useEffect(() => {
    const node = tiersRef.current;
    if (!node || scrolledEventFired.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !scrolledEventFired.current) {
          scrolledEventFired.current = true;
          trackEvent("paywall_scrolled_to_tiers");
          observer.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  async function handleSubscribe(
    priceId: string,
    plan: "founding" | "standard",
  ) {
    if (isPreview) {
      toast.info("Preview mode — checkout disabled", {
        id: "paywall-preview-mode",
        duration: Infinity,
      });
      return;
    }
    trackEvent("checkout_clicked", { plan });
    setLoading(priceId);
    setError(null);
    try {
      const email = user?.primaryEmailAddress?.emailAddress;
      const res = await createCheckoutSession(email, priceId);
      // B212: backend short-circuits when the user is already trialing/active.
      // Redirect to /today instead of attempting a second checkout.
      if (res.already_active) {
        window.location.href = res.redirect_url ?? "/today";
        return;
      }
      if (!res.checkout_url) {
        throw new Error("Checkout URL missing from response.");
      }
      window.location.href = res.checkout_url;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not start checkout. Try again.",
      );
      setLoading(null);
    }
  }

  return (
    <>
      <TopBar title="Subscribe" />

      {/* A285: no CTA leads here while billing is paused, but the URL still
          works and checkout is still live. Taking someone's money for what
          everyone else has for free is the one outcome worth spending ten
          lines to avoid — so say it plainly, above the prices. The tiers stay
          reachable: whoever still wants to subscribe may. */}
      {billingPaused && (
        <div className="mx-auto mt-4 max-w-md px-6">
          <div className="rounded-lg border border-border bg-primary/5 px-4 py-3 text-sm">
            <p className="font-medium">The app is free right now.</p>
            <p className="mt-1 text-muted-foreground">
              Billing is paused for everyone — you have full access without
              subscribing. Nothing below is needed.
            </p>
          </div>
        </div>
      )}

      <PaywallHero />

      <div className="mx-auto max-w-md">
        <ValueBullets />

        <div ref={tiersRef} className="space-y-5 px-6">
          <TierCard
            variant="founding"
            price="$4.99"
            priceInterval="/month"
            badge={foundingBadgeCopy()}
            tagline="Locked forever · founder pricing"
            bullets={[
              "Everything in Standard",
              "Price locked at $4.99 forever",
              "Founder badge on your profile",
            ]}
            ctaLabel="Start 15-day free trial"
            loading={loading === PRICE_ID_FOUNDER}
            disabled={loading !== null || isPreview}
            onCtaClick={() => handleSubscribe(PRICE_ID_FOUNDER, "founding")}
          />

          <TierCard
            variant="standard"
            price="$9.99"
            priceInterval="/month"
            tagline="Full access"
            bullets={[
              "Full AI-powered training plans",
              "Weekly plan adaptation",
              "Assessment every 6 weeks",
              "15-day free trial — no card required",
            ]}
            ctaLabel="Start free trial"
            loading={loading === PRICE_ID_STANDARD}
            disabled={loading !== null || isPreview}
            onCtaClick={() => handleSubscribe(PRICE_ID_STANDARD, "standard")}
          />
        </div>

        <p className="mt-6 px-8 text-center text-xs text-fg-muted">
          No card required to start your 15-day free trial. Add a payment
          method anytime before it ends — handled securely by Stripe (Apple
          Pay, Google Pay, and card). Cancel anytime from Settings.
        </p>

        {error && (
          <p className="mt-3 px-6 text-center text-sm text-destructive">
            {error}
          </p>
        )}

        <PaywallFAQ />
      </div>
    </>
  );
}
