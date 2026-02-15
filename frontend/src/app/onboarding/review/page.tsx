"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { completeOnboarding } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const WEAKNESS_LABELS: Record<string, string> = {
  pump_too_early: "Pompo troppo presto",
  fingers_give_out: "Le dita cedono",
  cant_hold_hard_moves: "Non tengo i movimenti duri",
  technique_errors: "Errori di tecnica",
  cant_read_routes: "Non leggo le vie",
  cant_manage_rests: "Non gestisco i riposi",
  lack_power: "Manca potenza esplosiva",
  injury_prone: "Infortuni frequenti",
};

function SummaryRow({
  label,
  value,
  editHref,
  router,
}: {
  label: string;
  value: string;
  editHref: string;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="text-sm">{value}</p>
      </div>
      <button
        type="button"
        className="shrink-0 text-xs text-primary hover:underline"
        onClick={() => router.push(editHref)}
      >
        Modifica
      </button>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { data } = useOnboarding();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Count tests entered
  const testCount = useMemo(() => {
    let count = 0;
    if (data.tests.max_hang_20mm_5s_total_kg != null) count++;
    if (data.tests.weighted_pullup_1rm_total_kg != null) count++;
    if (data.tests.repeater_7_3_max_sets_20mm != null) count++;
    return count;
  }, [data.tests]);

  // Count available slots
  const slotCount = useMemo(() => {
    let count = 0;
    for (const day of Object.values(data.availability)) {
      for (const slot of Object.values(day)) {
        if (slot.available) count++;
      }
    }
    return count;
  }, [data.availability]);

  // Count available days
  const dayCount = useMemo(() => {
    let count = 0;
    for (const day of Object.values(data.availability)) {
      const hasSlot = Object.values(day).some((s) => s.available);
      if (hasSlot) count++;
    }
    return count;
  }, [data.availability]);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      await completeOnboarding(data);
      setSuccess(true);
      // Brief delay to show success state, then redirect
      setTimeout(() => {
        router.push("/today");
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore durante la generazione del piano");
      setLoading(false);
    }
  };

  // Test values summary
  const testValues = useMemo(() => {
    const parts: string[] = [];
    if (data.tests.max_hang_20mm_5s_total_kg != null)
      parts.push(`Max Hang: ${data.tests.max_hang_20mm_5s_total_kg}kg`);
    if (data.tests.weighted_pullup_1rm_total_kg != null)
      parts.push(`Pull-up: ${data.tests.weighted_pullup_1rm_total_kg}kg`);
    if (data.tests.repeater_7_3_max_sets_20mm != null)
      parts.push(`Repeater: ${data.tests.repeater_7_3_max_sets_20mm} reps`);
    return parts.length > 0 ? parts.join(", ") : "";
  }, [data.tests]);

  if (success) {
    return (
      <div className="mx-auto max-w-lg space-y-6 pt-8">
        <Card>
          <CardContent className="py-12 text-center space-y-4">
            <p className="text-2xl font-semibold">Piano generato!</p>
            <p className="text-muted-foreground">Reindirizzamento in corso...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Riepilogo</CardTitle>
        </CardHeader>
        <CardContent className="divide-y">
          {/* Profilo */}
          <SummaryRow
            label="Profilo"
            value={`${data.profile.name}, ${data.profile.weight_kg}kg, ${data.profile.height_cm}cm${data.profile.body_fat_pct ? `, ${data.profile.body_fat_pct}% BF` : ""}`}
            editHref="/onboarding/profile"
            router={router}
          />

          {/* Esperienza */}
          <SummaryRow
            label="Esperienza"
            value={`${data.experience.climbing_years} anni di arrampicata, ${data.experience.structured_training_years} anni allenamento strutturato`}
            editHref="/onboarding/experience"
            router={router}
          />

          {/* Gradi */}
          <SummaryRow
            label="Gradi"
            value={`Lead RP: ${data.grades.lead_max_rp}, OS: ${data.grades.lead_max_os}${data.grades.boulder_max_rp ? `, Boulder RP: ${data.grades.boulder_max_rp}` : ""}${data.grades.boulder_max_os ? `, OS: ${data.grades.boulder_max_os}` : ""}`}
            editHref="/onboarding/grades"
            router={router}
          />

          {/* Obiettivo */}
          <SummaryRow
            label="Obiettivo"
            value={`${data.goal.target_grade} ${data.goal.discipline} (${data.goal.target_style}), entro ${data.goal.deadline}`}
            editHref="/onboarding/goals"
            router={router}
          />

          {/* Debolezze */}
          <SummaryRow
            label="Debolezze"
            value={`${WEAKNESS_LABELS[data.self_eval.primary_weakness] ?? data.self_eval.primary_weakness}, ${WEAKNESS_LABELS[data.self_eval.secondary_weakness] ?? data.self_eval.secondary_weakness}`}
            editHref="/onboarding/weaknesses"
            router={router}
          />

          {/* Test */}
          <SummaryRow
            label="Test"
            value={
              testCount === 0
                ? "Nessun test inserito"
                : `${testCount}/3 test${testValues ? ` (${testValues})` : ""}`
            }
            editHref="/onboarding/tests"
            router={router}
          />

          {/* Limitazioni */}
          <SummaryRow
            label="Limitazioni"
            value={
              data.limitations.length === 0
                ? "Nessuna"
                : `${data.limitations.length} limitazione${data.limitations.length > 1 ? "i" : ""}`
            }
            editHref="/onboarding/limitations"
            router={router}
          />

          {/* Location */}
          <SummaryRow
            label="Location"
            value={`Casa: ${data.equipment.home_enabled ? `${data.equipment.home.length} attrezzi` : "no"}, ${data.equipment.gyms.length} palestra${data.equipment.gyms.length !== 1 ? "e" : ""}`}
            editHref="/onboarding/locations"
            router={router}
          />

          {/* Disponibilita */}
          <SummaryRow
            label="Disponibilita"
            value={`${dayCount} giorni, ${slotCount} slot totali`}
            editHref="/onboarding/availability"
            router={router}
          />

          {/* Trip */}
          <SummaryRow
            label="Trip"
            value={
              data.trips.length === 0
                ? "Nessuno"
                : `${data.trips.length} trip pianificato${data.trips.length > 1 ? "i" : ""}`
            }
            editHref="/onboarding/trips"
            router={router}
          />
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-600 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/trips")}
          disabled={loading}
        >
          Indietro
        </Button>
        <Button
          size="lg"
          disabled={loading}
          onClick={handleGenerate}
        >
          {loading ? "Generazione in corso..." : "Genera il tuo piano"}
        </Button>
      </div>
    </div>
  );
}
