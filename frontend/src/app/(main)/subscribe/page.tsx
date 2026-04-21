"use client";

import { useEffect, useState } from "react";
import { useUser } from "@clerk/nextjs";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createCheckoutSession } from "@/lib/api";
import { captureUtmOnMount, trackEvent } from "@/lib/analytics";

const PRICE_ID_FOUNDER = process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_FOUNDER ?? "";
const PRICE_ID_STANDARD =
  process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_STANDARD ?? "";

export default function SubscribePage() {
  const { user } = useUser();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureUtmOnMount();
    trackEvent("subscribe_viewed");
  }, []);

  async function handleSubscribe(priceId: string, plan: "founding" | "standard") {
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

  const features = [
    "Personalised training plans built on 200+ scientific papers",
    "Guided sessions with step-by-step timer and voice cues",
    "Adapts to you — your plan evolves based on your feedback",
    "Indoor + outdoor — track gym sessions and crag days",
    "Proven methodology — Hörst periodisation used by elite coaches",
  ];

  return (
    <>
      <TopBar title="Subscribe" />
      <div className="p-4 space-y-6 max-w-md mx-auto">
        {/* Founding Climber — featured */}
        <Card className="border-primary ring-2 ring-primary/30">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xl">Founding Climber</CardTitle>
              <span className="rounded-full bg-primary/15 px-3 py-0.5 text-xs font-semibold text-primary">
                Limited
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold">$4.99</span>
              <span className="text-muted-foreground">/month</span>
            </div>

            <ul className="space-y-1.5 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">✓</span>
                <span>Locked at $4.99/mo forever</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">✓</span>
                <span>Only 20 spots available</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-0.5">✓</span>
                <span>15-day free trial</span>
              </li>
            </ul>

            <Button
              className="w-full"
              size="lg"
              onClick={() => handleSubscribe(PRICE_ID_FOUNDER, "founding")}
              disabled={loading !== null}
            >
              {loading === PRICE_ID_FOUNDER
                ? "Loading..."
                : "Start Free Trial"}
            </Button>
          </CardContent>
        </Card>

        {/* Standard */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xl">Standard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold">$9.99</span>
              <span className="text-muted-foreground">/month</span>
            </div>

            <p className="text-sm text-muted-foreground">
              Full access to AI-powered training plans. 15-day free trial.
            </p>

            <Button
              className="w-full"
              variant="outline"
              size="lg"
              onClick={() => handleSubscribe(PRICE_ID_STANDARD, "standard")}
              disabled={loading !== null}
            >
              {loading === PRICE_ID_STANDARD
                ? "Loading..."
                : "Start Free Trial"}
            </Button>
          </CardContent>
        </Card>

        {/* Feature list */}
        <div className="px-2">
          <p className="text-sm font-medium mb-3">
            Both plans include everything:
          </p>
          <ul className="space-y-2 text-sm">
            {features.map((feature) => (
              <li key={feature} className="flex items-start gap-2">
                <span className="text-primary mt-0.5">✓</span>
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-center text-muted-foreground px-4">
          Accepts Apple Pay, Google Pay, and card — handled securely by Stripe.
          Your card will be charged after the 15-day trial. Cancel anytime from
          Settings.
        </p>

        {error && (
          <p className="text-sm text-destructive text-center">{error}</p>
        )}
      </div>
    </>
  );
}
