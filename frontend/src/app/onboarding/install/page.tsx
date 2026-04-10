"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Compass,
  Globe,
  MoreHorizontal,
  MoreVertical,
  PlusCircle,
} from "lucide-react";

/* iOS share icon — square with arrow pointing up (not available in Lucide) */
function IosShareIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" />
      <polyline points="12 3 12 15" />
      <polyline points="8 7 12 3 16 7" />
    </svg>
  );
}

type Platform = "iphone" | "android";

const IPHONE_STEPS = [
  {
    icon: <Compass className="h-6 w-6" />,
    title: "Open this page in Safari or Chrome",
    text: "Safari is recommended. Chrome also works on iOS 16.4+.",
  },
  {
    icon: <IosShareIcon className="h-6 w-6" />,
    title: "Tap the Share button",
    text: (
      <>
        <strong>Safari:</strong> tap the share icon in the bottom toolbar.
        <br />
        <strong>Chrome:</strong> tap the share icon in the top-right corner.
      </>
    ),
  },
  {
    icon: (
      <div className="flex items-center gap-2">
        <MoreHorizontal className="h-6 w-6" />
        <span className="text-muted-foreground">&rarr;</span>
        <PlusCircle className="h-6 w-6" />
      </div>
    ),
    title: 'Tap "Add to Home Screen"',
    text: (
      <>
        <strong>Safari:</strong> scroll down, tap{" "}
        <span className="inline-flex items-center gap-1 rounded border border-muted-foreground/30 px-1.5 py-0.5 text-xs font-medium">
          <MoreHorizontal className="h-3.5 w-3.5" /> More
        </span>
        , then tap <strong>&quot;Add to Home Screen&quot;</strong>. If you
        don&apos;t see it, tap &quot;Edit Actions&quot; at the bottom to add it.
        <br />
        <strong>Chrome:</strong> tap <strong>&quot;Add to Home Screen&quot;</strong> directly
        from the share menu.
      </>
    ),
  },
];

const ANDROID_STEPS = [
  {
    icon: <Globe className="h-6 w-6" />,
    title: "Open this page in Chrome",
    text: "Make sure you're using Chrome.",
  },
  {
    icon: <MoreVertical className="h-6 w-6" />,
    title: "Tap the three-dot menu",
    text: "Tap the menu icon in the top-right corner.",
  },
  {
    icon: <PlusCircle className="h-6 w-6" />,
    title: '"Add to Home screen"',
    text: 'Select "Add to Home screen", then tap "Add".',
  },
];

export default function InstallPage() {
  const router = useRouter();
  const [platform, setPlatform] = useState<Platform>("iphone");

  const steps = platform === "iphone" ? IPHONE_STEPS : ANDROID_STEPS;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Add to Home Screen</CardTitle>
          <CardDescription>
            For the best experience, add Climb Agent to your home screen — it
            works just like a native app.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Platform tabs */}
          <div className="grid grid-cols-2 gap-3">
            {(["iphone", "android"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPlatform(p)}
                className={`rounded-lg border px-4 py-3 text-center text-base font-semibold transition-colors ${
                  platform === p
                    ? "border-primary ring-2 ring-primary/30 text-foreground"
                    : "border-muted text-muted-foreground hover:border-primary/50"
                }`}
              >
                {p === "iphone" ? "iPhone" : "Android"}
              </button>
            ))}
          </div>

          {/* Steps */}
          <ol className="space-y-5">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-4">
                {/* Number badge */}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-bold text-primary">
                  {i + 1}
                </div>

                <div className="space-y-1 pt-0.5">
                  <div className="flex items-center gap-2 text-foreground">
                    {step.icon}
                  </div>
                  <p className="text-sm font-medium text-foreground">
                    {step.title}
                  </p>
                  <p className="text-sm text-muted-foreground">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>

          {/* Hint */}
          <p className="text-xs text-muted-foreground text-center">
            Already installed? Just tap Next.
          </p>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/welcome")}
        >
          Back
        </Button>
        <Button onClick={() => router.push("/onboarding/profile")}>
          Next
        </Button>
      </div>
    </div>
  );
}
