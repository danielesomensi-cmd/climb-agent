"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function WelcomePage() {
  const router = useRouter();

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Welcome to Climb Agent</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-lg font-medium text-foreground">
            Intelligent training, built for serious climbers
          </p>

          <p className="text-sm text-muted-foreground">
            Climb Agent uses AI-driven periodization to build a training plan
            tailored to your strengths, weaknesses, and schedule. The more
            complete your initial assessment, the better. Your plan also adapts
            from session feedback over time.
          </p>

          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Maps your strengths and weaknesses across 5 performance axes
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Builds a periodized macrocycle matched to your goal and timeline
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Adapts every week based on your session feedback
            </li>
          </ul>
        </CardContent>
      </Card>

      <div className="flex flex-col items-end gap-3">
        <Button onClick={() => router.push("/onboarding/install")}>
          Let&apos;s start
        </Button>
        <button
          onClick={() => router.push("/onboarding/recover")}
          className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          Already have an account? Recover access
        </button>
      </div>
    </div>
  );
}
