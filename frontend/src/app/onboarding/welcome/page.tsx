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
          <p className="text-muted-foreground">
            Climb Agent helps you improve at climbing with a training plan
            built specifically for you.
          </p>

          <p className="text-sm text-muted-foreground">
            The more complete your initial assessment, the more personalized
            your training plan will be. Climb Agent will also learn from your
            session feedback and refine your plan over time.
          </p>

          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Analyzes your current level
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Creates a personalized training plan
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1 block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              Adapts to your feedback week after week
            </li>
          </ul>
        </CardContent>
      </Card>

      <div className="flex flex-col items-end gap-3">
        <Button onClick={() => router.push("/onboarding/profile")}>
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
