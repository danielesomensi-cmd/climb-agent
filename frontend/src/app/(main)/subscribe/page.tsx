"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createCheckoutSession } from "@/lib/api";

export default function SubscribePage() {
  const { user } = useUser();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubscribe() {
    setLoading(true);
    setError(null);
    try {
      const email = user?.primaryEmailAddress?.emailAddress;
      const { checkout_url } = await createCheckoutSession(email);
      window.location.href = checkout_url;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not start checkout. Try again."
      );
      setLoading(false);
    }
  }

  return (
    <>
      <TopBar title="Subscribe" />
      <div className="p-4 space-y-6 max-w-md mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">climb-agent Pro</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold">€9.99</span>
              <span className="text-muted-foreground">/month</span>
            </div>

            <p className="text-sm text-muted-foreground">
              14-day free trial — card required, cancel anytime.
            </p>

            <ul className="space-y-2 text-sm">
              {[
                "Personalised weekly training plans",
                "Guided session timer with voice cues",
                "Closed-loop progression tracking",
                "Outdoor session logging",
                "Free climbing session tracker",
              ].map((feature) => (
                <li key={feature} className="flex items-start gap-2">
                  <span className="text-primary mt-0.5">✓</span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <div className="pt-2">
              <p className="text-xs text-muted-foreground mb-3">
                Accepts Apple Pay, Google Pay, and card — handled securely by
                Stripe.
              </p>
              <Button
                className="w-full"
                size="lg"
                onClick={handleSubscribe}
                disabled={loading}
              >
                {loading ? "Loading..." : "Start 14-day free trial"}
              </Button>
            </div>

            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}
          </CardContent>
        </Card>

        <p className="text-xs text-center text-muted-foreground px-4">
          By subscribing you agree to our Terms of Service. Your card will be
          charged €9.99/month after the 14-day trial. Cancel anytime from
          Settings.
        </p>
      </div>
    </>
  );
}
