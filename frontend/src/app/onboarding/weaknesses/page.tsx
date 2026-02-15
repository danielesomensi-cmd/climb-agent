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
    title: "Pompo troppo presto",
    description: "I miei avambracci si gonfiano prima che la forza ceda",
  },
  {
    id: "fingers_give_out",
    title: "Le dita cedono",
    description: "La forza delle dita e il mio limite principale",
  },
  {
    id: "cant_hold_hard_moves",
    title: "Non tengo i movimenti duri",
    description: "Mi manca forza/potenza sui singoli movimenti crux",
  },
  {
    id: "technique_errors",
    title: "Errori di tecnica",
    description: "Cado per posizione del corpo o movimenti sbagliati",
  },
  {
    id: "cant_read_routes",
    title: "Non leggo le vie",
    description: "Fatico a trovare la beta e leggere le sequenze",
  },
  {
    id: "cant_manage_rests",
    title: "Non gestisco i riposi",
    description: "Non recupero bene sulle soste",
  },
  {
    id: "lack_power",
    title: "Manca potenza esplosiva",
    description: "Movimenti dinamici e lanci sono il mio punto debole",
  },
  {
    id: "injury_prone",
    title: "Infortuni frequenti",
    description: "Problemi fisici limitano il mio allenamento",
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
            Qual e il tuo punto debole principale?
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
              E la tua seconda debolezza?
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
          Indietro
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/tests")}
        >
          Avanti
        </Button>
      </div>
    </div>
  );
}
