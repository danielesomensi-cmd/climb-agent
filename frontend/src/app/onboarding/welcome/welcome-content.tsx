"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { SignInButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InAppBrowserBanner } from "@/components/install/in-app-browser-banner";

export function WelcomeContent() {
  const router = useRouter();

  return (
    <>
      {/* A261 — above the hero on purpose: inside an Instagram/Facebook webview
          the "Start assessment" CTA leads to a sign-up that Google will refuse,
          so the warning has to arrive before the tap, not after. Renders
          nothing in a normal browser. */}
      <InAppBrowserBanner />

      <section className="relative -mx-4 h-[55vh] overflow-hidden">
        <Image
          src="/hero/onboarding_hero.webp"
          alt="Climber atop a mountain at sunrise"
          fill
          priority
          sizes="(max-width: 768px) 100vw, 768px"
          className="object-cover"
        />
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(to bottom, transparent 35%, hsl(var(--surface-base) / 0.95) 100%)",
          }}
          aria-hidden="true"
        />
        <div className="absolute inset-x-0 bottom-0 p-6 pb-8">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-fg md:text-4xl">
            Periodized training.
          </h1>
          <p className="mt-2 text-base text-fg-secondary md:text-lg">
            Built for climbers chasing hard grades.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-lg space-y-6 pt-6">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <p className="text-sm text-muted-foreground">
              climb-agent uses deterministic periodization based on Hörst 4-3-2-1 to build a plan from your assessment, weaknesses, and schedule. Every session you log adapts the next.
            </p>

            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                5-axis assessment: finger strength, pulling, power-endurance, technique, endurance
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                10–13 week macrocycle: base → strength → power-endurance → performance → deload
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                Closed-loop adaptation: every session feedback adjusts the next week
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                AI coach: conversational guidance built on your plan and training data
              </li>
            </ul>
          </CardContent>
        </Card>

        <div className="flex flex-col items-end gap-3">
          {/* A256 — was a <SignUpButton>: the very first tap on the landing
              page opened a sign-up form, before the visitor had seen anything
              the product does. The wizard is public now; the account is asked
              for on the review page, where there is something to save. */}
          <Button onClick={() => router.push("/onboarding/profile")}>
            Start assessment
          </Button>
          {/* B300 — a returning, signed-out user (new device, cleared cookies)
              needs an obvious way back in now that the root routes here instead
              of straight to /sign-in. */}
          <SignInButton mode="redirect" forceRedirectUrl="/">
            <button className="text-sm font-medium text-primary underline underline-offset-2 hover:text-primary/80">
              Already have an account? Sign in
            </button>
          </SignInButton>
          {/* B320 — a third link used to sit here, "Lost access? Recover with
              a code". The code it referred to stopped existing when Clerk took
              over recovery, so the link led to a page that only bounced to
              /sign-in. Signing in with the original email IS the recovery
              path, and that is the link above. */}
        </div>
      </div>
    </>
  );
}
