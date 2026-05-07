"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { SignUpButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function WelcomeContent() {
  const router = useRouter();

  return (
    <>
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
            Built for the top 5%.
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
                AI coach coming soon: conversational guidance built on your training data
              </li>
            </ul>
          </CardContent>
        </Card>

        <div className="flex flex-col items-end gap-3">
          <SignUpButton mode="redirect" forceRedirectUrl="/onboarding/install">
            <Button>Start assessment</Button>
          </SignUpButton>
          <button
            onClick={() => router.push("/onboarding/recover")}
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Already have an account? Recover access
          </button>
        </div>
      </div>
    </>
  );
}
