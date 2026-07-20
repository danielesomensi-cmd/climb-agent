"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { getState, setStartWeek } from "@/lib/api";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import type { Phase } from "@/lib/types";

interface PhaseOption {
  offset: number;
  label: string;
}

function buildPhaseOptions(phases: Phase[]): PhaseOption[] {
  const options: PhaseOption[] = [];
  let cumulativeWeeks = 0;
  for (const phase of phases) {
    if (phase.phase_id === "deload") {
      cumulativeWeeks += phase.duration_weeks;
      continue; // skip deload — not a useful start point
    }
    options.push({
      offset: cumulativeWeeks,
      label:
        cumulativeWeeks === 0
          ? `Start fresh — Week 1 (${phase.phase_name})`
          : `Skip to ${phase.phase_name} — Week ${cumulativeWeeks + 1}`,
    });
    cumulativeWeeks += phase.duration_weeks;
  }
  return options;
}

export default function StartWeekPage() {
  const router = useRouter();
  const { isLoaded: authReady } = useAuth();
  const { canInteract, loading: subLoading } = useSubscription();
  const [options, setOptions] = useState<PhaseOption[]>([]);
  const [selected, setSelected] = useState("0");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  // A245 C-6 (F28) — true when we fell back to the default option because the
  // state fetch failed; the user must know their phases weren't loaded.
  const [loadFailed, setLoadFailed] = useState(false);

  // A-ACTIVATION-TIMING: route to /today if already trialing/active,
  // /subscribe otherwise. Previous unconditional /subscribe redirect
  // trapped paying users re-entering the onboarding flow.
  const routeNext = () => {
    if (subLoading) return;
    router.push(canInteract ? "/today" : "/subscribe");
  };

  // B155: gate on Clerk readiness
  useEffect(() => {
    if (!authReady) return;
    getState()
      .then((state) => {
        const phases = state.macrocycle?.phases ?? [];
        if (phases.length > 0) {
          setOptions(buildPhaseOptions(phases));
        } else {
          setOptions([{ offset: 0, label: "Start fresh — Week 1" }]);
        }
      })
      // A245 C-6 (F28) — this promise had no .catch, so going offline right
      // after submitting onboarding left `ready` false forever and the page
      // rendered `return null`: a white screen at the very last step of the
      // funnel, with no way forward. Degrade to the default option instead.
      .catch((err) => {
        console.error("start-week: could not load state, using default option:", err);
        setOptions([{ offset: 0, label: "Start fresh — Week 1" }]);
        setLoadFailed(true);
      })
      .finally(() => setReady(true));
  }, [authReady]);

  const handleContinue = async () => {
    const offset = parseInt(selected, 10);
    setLoading(true);
    try {
      if (offset > 0) {
        await setStartWeek(offset);
      }
      routeNext();
    } catch {
      routeNext();
    } finally {
      setLoading(false);
    }
  };

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Where to start</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            If you&apos;ve already been following a structured training plan, you can
            skip ahead and start from a later phase.
          </p>

          {loadFailed && (
            <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-400">
              We couldn&apos;t load your plan phases just now. You can continue
              from Week 1 — you can always change where you start later in
              Settings.
            </p>
          )}

          <RadioGroup value={selected} onValueChange={setSelected}>
            {options.map((opt) => (
              <div key={opt.offset} className="flex items-center space-x-3 py-2">
                <RadioGroupItem value={String(opt.offset)} id={`phase-${opt.offset}`} />
                <Label htmlFor={`phase-${opt.offset}`} className="cursor-pointer">
                  {opt.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          disabled={loading}
          onClick={routeNext}
        >
          Skip
        </Button>
        <Button size="lg" disabled={loading} onClick={handleContinue}>
          {loading ? "Applying..." : "Continue"}
        </Button>
      </div>
    </div>
  );
}
