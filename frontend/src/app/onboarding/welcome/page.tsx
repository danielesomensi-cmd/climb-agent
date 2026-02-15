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

      <div className="flex justify-end">
        <Button onClick={() => router.push("/onboarding/profile")}>
          Let's start
        </Button>
      </div>
    </div>
  );
}
