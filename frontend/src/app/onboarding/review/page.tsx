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

const LEAD_GRADES_ORDERED = [
  "5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

function gradeToNumeric(grade: string): number {
  const idx = LEAD_GRADES_ORDERED.indexOf(grade);
  return idx >= 0 ? idx : -1;
}

const CLIMBING_EQUIPMENT = new Set([
  "gym_boulder", "gym_routes", "spraywall",
  "board_moonboard", "board_kilter", "campus_board",
]);

const WEAKNESS_LABELS: Record<string, string> = {
  pump_too_early: "I pump out too early",
  fingers_give_out: "My fingers give out",
  cant_hold_hard_moves: "Can't hold hard moves",
  technique_errors: "Technique errors",
  cant_read_routes: "Can't read routes",
  cant_manage_rests: "Can't manage rests",
  lack_power: "Lack explosive power",
  injury_prone: "Frequent injuries",
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
        Edit
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

  // Cross-validation warnings
  const hasGradeExperienceMismatch = useMemo(() => {
    if (data.experience.climbing_years > 0) return false;
    const gradeNum = gradeToNumeric(data.grades.lead_max_rp);
    const threshold = gradeToNumeric("6a");
    return gradeNum >= 0 && threshold >= 0 && gradeNum > threshold;
  }, [data.experience.climbing_years, data.grades.lead_max_rp]);

  const hasNoClimbingEquipment = useMemo(() => {
    return !data.equipment.gyms.some((gym) =>
      gym.equipment.some((eq) => CLIMBING_EQUIPMENT.has(eq))
    );
  }, [data.equipment.gyms]);

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
      setError(err instanceof Error ? err.message : "Error generating the plan");
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
            <p className="text-2xl font-semibold">Plan generated!</p>
            <p className="text-muted-foreground">Redirecting...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Summary</CardTitle>
        </CardHeader>
        <CardContent className="divide-y">
          {/* Profile */}
          <SummaryRow
            label="Profile"
            value={`${data.profile.name}, ${data.profile.weight_kg}kg, ${data.profile.height_cm}cm${data.profile.body_fat_pct ? `, ${data.profile.body_fat_pct}% BF` : ""}`}
            editHref="/onboarding/profile"
            router={router}
          />

          {/* Experience */}
          <SummaryRow
            label="Experience"
            value={`${data.experience.climbing_years} years climbing, ${data.experience.structured_training_years} years structured training`}
            editHref="/onboarding/experience"
            router={router}
          />

          {/* Grades */}
          <SummaryRow
            label="Grades"
            value={`Lead RP: ${data.grades.lead_max_rp}, OS: ${data.grades.lead_max_os}${data.grades.boulder_max_rp ? `, Boulder RP: ${data.grades.boulder_max_rp}` : ""}${data.grades.boulder_max_os ? `, OS: ${data.grades.boulder_max_os}` : ""}`}
            editHref="/onboarding/grades"
            router={router}
          />

          {/* Goal */}
          <SummaryRow
            label="Goal"
            value={`${data.goal.target_grade} ${data.goal.discipline} (${data.goal.target_style}), by ${data.goal.deadline}`}
            editHref="/onboarding/goals"
            router={router}
          />

          {/* Weaknesses */}
          <SummaryRow
            label="Weaknesses"
            value={`${WEAKNESS_LABELS[data.self_eval.primary_weakness] ?? data.self_eval.primary_weakness}, ${WEAKNESS_LABELS[data.self_eval.secondary_weakness] ?? data.self_eval.secondary_weakness}`}
            editHref="/onboarding/weaknesses"
            router={router}
          />

          {/* Tests */}
          <SummaryRow
            label="Tests"
            value={
              testCount === 0
                ? "No tests entered"
                : `${testCount}/3 test${testValues ? ` (${testValues})` : ""}`
            }
            editHref="/onboarding/tests"
            router={router}
          />

          {/* Limitations */}
          <SummaryRow
            label="Limitations"
            value={
              data.limitations.length === 0
                ? "None"
                : `${data.limitations.length} limitation${data.limitations.length > 1 ? "s" : ""}`
            }
            editHref="/onboarding/limitations"
            router={router}
          />

          {/* Location */}
          <SummaryRow
            label="Location"
            value={`Home: ${data.equipment.home_enabled ? `${data.equipment.home.length} items` : "no"}, ${data.equipment.gyms.length} gym${data.equipment.gyms.length !== 1 ? "s" : ""}`}
            editHref="/onboarding/locations"
            router={router}
          />

          {/* Availability */}
          <SummaryRow
            label="Availability"
            value={`${dayCount} days, ${slotCount} total slots`}
            editHref="/onboarding/availability"
            router={router}
          />

          {/* Trip */}
          <SummaryRow
            label="Trip"
            value={
              data.trips.length === 0
                ? "None"
                : `${data.trips.length} trip${data.trips.length > 1 ? "s" : ""} planned`
            }
            editHref="/onboarding/trips"
            router={router}
          />
        </CardContent>
      </Card>

      {/* Warnings */}
      {hasGradeExperienceMismatch && (
        <div className="rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
          Your grades suggest significant climbing experience. Please review your experience inputs.
        </div>
      )}

      {hasNoClimbingEquipment && data.equipment.gyms.length > 0 && (
        <div className="rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
          None of your gyms have climbing walls. Climbing-specific sessions will be limited. Consider adding a gym with bouldering or route areas.
        </div>
      )}

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
          Back
        </Button>
        <Button
          size="lg"
          disabled={loading}
          onClick={handleGenerate}
        >
          {loading ? "Generating..." : "Generate your plan"}
        </Button>
      </div>
    </div>
  );
}
