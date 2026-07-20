"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { StepNav } from "@/components/onboarding/step-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface WeaknessItem {
  id: string;
  title: string;
  description: string;
  scope: "universal" | "lead" | "boulder";
}

const ALL_WEAKNESSES: WeaknessItem[] = [
  // Universal
  {
    id: "fingers_give_out",
    title: "My fingers give out",
    description: "Finger strength is my main limiter",
    scope: "universal",
  },
  {
    id: "cant_hold_hard_moves",
    title: "Can't hold hard moves",
    description: "I lack strength/power on single crux moves",
    scope: "universal",
  },
  {
    id: "technique_errors",
    title: "Technique errors",
    description: "I fall due to body position or movement mistakes",
    scope: "universal",
  },
  {
    id: "lack_power",
    title: "Lack explosive power",
    description: "Dynamic moves and dynos are my weak point",
    scope: "universal",
  },
  {
    id: "injury_prone",
    title: "Frequent injuries",
    description: "Physical issues limit my training",
    scope: "universal",
  },
  // Lead-only
  {
    id: "pump_too_early",
    title: "I pump out too early",
    description: "My forearms pump before my strength gives out",
    scope: "lead",
  },
  {
    id: "cant_read_routes",
    title: "Can't read routes",
    description: "I struggle to find the beta and read sequences",
    scope: "lead",
  },
  {
    id: "cant_manage_rests",
    title: "Can't manage rests",
    description: "I don't recover well on rest stances",
    scope: "lead",
  },
  // Boulder-only
  {
    id: "poor_body_tension",
    title: "Poor body tension",
    description: "I can't maintain tension on steep terrain, feet cut",
    scope: "boulder",
  },
  {
    id: "poor_dynamic_movement",
    title: "Poor dynamic movement",
    description: "I struggle with coordination moves and dynos",
    scope: "boulder",
  },
  {
    id: "weak_on_slopers",
    title: "Weak on slopers",
    description: "I struggle on rounded or open-hand holds",
    scope: "boulder",
  },
  {
    id: "poor_problem_reading",
    title: "Poor problem reading",
    description: "I can't read sequences or find beta efficiently",
    scope: "boulder",
  },
];

function WeaknessCard({
  item,
  selected,
  disabled,
  onSelect,
}: {
  item: WeaknessItem;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <Card
      className={`cursor-pointer transition-colors ${
        selected
          ? "border-brand bg-brand/5"
          : disabled
            ? "opacity-40 cursor-not-allowed"
            : "hover:border-brand/50"
      }`}
      onClick={() => {
        if (!disabled) onSelect();
      }}
    >
      <CardContent className="py-2 px-3">
        <p className="text-sm font-medium leading-tight">{item.title}</p>
        <p className="text-xs text-muted-foreground leading-tight">{item.description}</p>
      </CardContent>
    </Card>
  );
}

export default function WeaknessesPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const selfEval = data.self_eval;
  const discipline = data.goal.discipline || "lead";

  // Filter weaknesses by discipline
  const weaknesses = useMemo(() => {
    return ALL_WEAKNESSES.filter((w) => {
      if (w.scope === "universal") return true;
      if (discipline === "both") return true;
      return w.scope === discipline;
    });
  }, [discipline]);

  const setPrimary = (id: string) => {
    const next = selfEval.primary_weakness === id ? "" : id;
    update("self_eval", {
      ...selfEval,
      primary_weakness: next,
      // Clear secondary if it conflicts or is no longer in scope
      secondary_weakness:
        selfEval.secondary_weakness === next ? "" : selfEval.secondary_weakness,
    });
  };

  const setSecondary = (id: string) => {
    const next = selfEval.secondary_weakness === id ? "" : id;
    update("self_eval", {
      ...selfEval,
      secondary_weakness: next,
    });
  };

  // A245 Phase D (F18) — secondary was REQUIRED, and its card only appeared
  // after picking a primary: the user saw a grey Next with no idea a second
  // card was even coming. It is now optional (the engine's _weakness_penalty
  // simply finds no match for an empty value).
  const blockers = selfEval.primary_weakness === ""
    ? ["Pick your primary weakness"]
    : [];

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      {/* Primary weakness */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            Primary weakness
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {weaknesses.map((w) => (
            <WeaknessCard
              key={w.id}
              item={w}
              selected={selfEval.primary_weakness === w.id}
              disabled={false}
              onSelect={() => setPrimary(w.id)}
            />
          ))}
        </CardContent>
      </Card>

      {/* Secondary weakness */}
      {selfEval.primary_weakness !== "" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Secondary weakness{" "}
              <span className="text-sm font-normal text-muted-foreground">
                (optional)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {weaknesses.map((w) => (
              <WeaknessCard
                key={w.id}
                item={w}
                selected={selfEval.secondary_weakness === w.id}
                disabled={w.id === selfEval.primary_weakness}
                onSelect={() => setSecondary(w.id)}
              />
            ))}
          </CardContent>
        </Card>
      )}

      <StepNav
        backHref="/onboarding/goals"
        nextHref="/onboarding/tests"
        blockers={blockers}
      />
    </div>
  );
}
