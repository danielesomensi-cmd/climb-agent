"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface WeaknessItem {
  id: string;
  title: string;
  description: string;
}

const WEAKNESSES: WeaknessItem[] = [
  {
    id: "pump_too_early",
    title: "I pump out too early",
    description: "My forearms pump before my strength gives out",
  },
  {
    id: "fingers_give_out",
    title: "My fingers give out",
    description: "Finger strength is my main limiter",
  },
  {
    id: "cant_hold_hard_moves",
    title: "Can't hold hard moves",
    description: "I lack strength/power on single crux moves",
  },
  {
    id: "technique_errors",
    title: "Technique errors",
    description: "I fall due to body position or movement mistakes",
  },
  {
    id: "cant_read_routes",
    title: "Can't read routes",
    description: "I struggle to find the beta and read sequences",
  },
  {
    id: "cant_manage_rests",
    title: "Can't manage rests",
    description: "I don't recover well on rest stances",
  },
  {
    id: "lack_power",
    title: "Lack explosive power",
    description: "Dynamic moves and dynos are my weak point",
  },
  {
    id: "injury_prone",
    title: "Frequent injuries",
    description: "Physical issues limit my training",
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
          ? "border-primary ring-2 ring-primary/30"
          : disabled
            ? "opacity-40 cursor-not-allowed"
            : "hover:border-primary/50"
      }`}
      onClick={() => {
        if (!disabled) onSelect();
      }}
    >
      <CardContent className="py-3 px-4">
        <p className="text-sm font-medium">{item.title}</p>
        <p className="text-xs text-muted-foreground">{item.description}</p>
      </CardContent>
    </Card>
  );
}

export default function WeaknessesPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const selfEval = data.self_eval;

  const setPrimary = (id: string) => {
    const next = selfEval.primary_weakness === id ? "" : id;
    update("self_eval", {
      ...selfEval,
      primary_weakness: next,
      // Clear secondary if it conflicts
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

  const isValid =
    selfEval.primary_weakness !== "" && selfEval.secondary_weakness !== "";

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      {/* Primary weakness */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            What is your main weakness?
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {WEAKNESSES.map((w) => (
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
              And your second weakness?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {WEAKNESSES.map((w) => (
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

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/goals")}
        >
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/tests")}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
