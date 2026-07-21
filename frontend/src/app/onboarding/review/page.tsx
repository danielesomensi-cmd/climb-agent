"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { submitOnboarding } from "@/lib/onboarding-submit";
import { profileErrors } from "@/lib/profile-validation";
import { getAttribution } from "@/lib/analytics";
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
  poor_body_tension: "Poor body tension",
  poor_dynamic_movement: "Poor dynamic movement",
  weak_on_slopers: "Weak on slopers",
  poor_problem_reading: "Poor problem reading",
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
      {/* A245 Phase D (F47): ?from=review lets the step offer a one-tap return
          instead of making the user walk the rest of the wizard. */}
      <button
        type="button"
        className="-m-2 shrink-0 p-2 text-xs text-primary hover:underline"
        onClick={() => router.push(`${editHref}?from=review`)}
      >
        Edit
      </button>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { data, clearDraft } = useOnboarding();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  // A245 Phase D (F17): false when an immediate retry cannot help (rate limit,
  // expired session) — the CTA says so instead of inviting a doomed tap.
  const [retryable, setRetryable] = useState(true);

  // Count tests entered
  const testCount = useMemo(() => {
    let count = 0;
    if ((data.tests.max_hang_20mm_7s_total_kg ?? data.tests.max_hang_20mm_5s_total_kg) != null) count++;
    if (data.tests.weighted_pullup_1rm_total_kg != null) count++;
    if (data.tests.repeater_7_3_max_sets_20mm != null) count++;
    if (data.tests.max_hang_duration_20mm_seconds != null) count++;
    if (data.tests.l_sit_hold_seconds != null) count++;
    if (data.tests.hip_flexibility_cm != null) count++;
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

  // B293 — the summary is the last gate before submit. A draft corrupted by a
  // mid-wizard re-auth used to sail through here as "0y, 0kg, 0cm" and poison
  // the engine baselines. Same bounds as the profile step + server guard.
  const profileProblems = useMemo(() => profileErrors(data.profile), [data.profile]);

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

  /**
   * A245 Phase D (F17) — one submit path for both CTAs. They were two
   * byte-identical handlers differing only in a flag and a destination, which
   * is how the same raw-error bug came to exist twice.
   */
  const submit = async (opts: { testWeek?: boolean; destination: string }) => {
    setLoading(true);
    setError(null);
    const result = await submitOnboarding(
      { ...data, attribution: getAttribution() },
      { testWeek: opts.testWeek },
    );
    if (!result.ok) {
      setError(result.message);
      setRetryable(result.retryable);
      setLoading(false);
      return;
    }
    clearDraft();
    setSuccess(true);
    setTimeout(() => router.push(opts.destination), 1500);
  };

  const handleGenerate = () => submit({ destination: "/onboarding/start-week" });
  const handleTestWeek = () => submit({ testWeek: true, destination: "/plan" });

  // Test values summary
  const testValues = useMemo(() => {
    const parts: string[] = [];
    const maxHangVal = data.tests.max_hang_20mm_7s_total_kg ?? data.tests.max_hang_20mm_5s_total_kg;
    if (maxHangVal != null)
      parts.push(`Max Hang: ${maxHangVal}kg`);
    if (data.tests.weighted_pullup_1rm_total_kg != null)
      parts.push(`Pull-up: ${data.tests.weighted_pullup_1rm_total_kg}kg`);
    if (data.tests.repeater_7_3_max_sets_20mm != null)
      parts.push(`Repeater: ${data.tests.repeater_7_3_max_sets_20mm} reps`);
    if (data.tests.max_hang_duration_20mm_seconds != null)
      parts.push(`Duration: ${data.tests.max_hang_duration_20mm_seconds}s`);
    if (data.tests.l_sit_hold_seconds != null)
      parts.push(`L-sit: ${data.tests.l_sit_hold_seconds}s`);
    if (data.tests.hip_flexibility_cm != null)
      parts.push(`Flex: ${data.tests.hip_flexibility_cm}cm`);
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
            value={`${data.profile.name}, ${data.profile.age}y, ${data.profile.weight_kg}kg, ${data.profile.height_cm}cm`}
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
            value={(() => {
              const parts: string[] = [];
              if (data.grades.lead_max_rp || data.grades.lead_max_os) {
                parts.push(`Lead RP: ${data.grades.lead_max_rp || "—"}, OS: ${data.grades.lead_max_os || "—"}`);
              }
              if (data.grades.boulder_max_rp || data.grades.boulder_max_os) {
                parts.push(`Boulder RP: ${data.grades.boulder_max_rp || "—"}, OS: ${data.grades.boulder_max_os || "—"}`);
              }
              return parts.join(" · ") || "—";
            })()}
            editHref="/onboarding/grades"
            router={router}
          />

          {/* Goal */}
          <SummaryRow
            label="Goal"
            value={(() => {
              const g = data.goal;
              const parts = [];
              if (g.discipline === "both") {
                parts.push(`Lead ${g.target_grade}`);
                if (g.target_boulder_grade) parts.push(`Boulder ${g.target_boulder_grade}`);
                parts.push(`(${g.target_style})`);
              } else {
                parts.push(`${g.target_grade} ${g.discipline}`);
                if (g.discipline !== "boulder") parts.push(`(${g.target_style})`);
              }
              parts.push(`${g.total_weeks ?? 12} weeks`);
              return parts.join(" ");
            })()}
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
                : `${testCount}/6 test${testCount !== 1 ? "s" : ""}${testValues ? ` (${testValues})` : ""}`
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

      {/* B293 — blocking: profile data missing or out of bounds */}
      {profileProblems.length > 0 && (
        <div
          role="alert"
          className="space-y-3 rounded-md border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          <p className="font-medium">Your profile needs fixing before we can build a plan:</p>
          <ul className="list-disc pl-5 space-y-0.5">
            {profileProblems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          <Button
            variant="outline"
            className="min-h-[44px] w-full text-sm"
            onClick={() => router.push("/onboarding/profile?from=review")}
          >
            Fix profile
          </Button>
        </div>
      )}

      {/* Warnings */}
      {hasGradeExperienceMismatch && (
        <div className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          Your grades suggest more climbing experience than you&apos;ve reported. Double-check the experience step.
        </div>
      )}

      {hasNoClimbingEquipment && data.equipment.gyms.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          No gym has bouldering or route walls. Climbing-specific sessions will be skipped. Add a gym with these in the Locations step.
        </div>
      )}

      {/* A245 Phase D (F17) — this used to render whatever string came back,
          which at the highest-intent moment in the product meant the user read
          `API 422: {"detail":"Macrocycle generation failed: ..."}`. */}
      {error && (
        <div
          role="alert"
          className="space-y-3 rounded-md border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          <p>{error}</p>
          <p className="text-xs text-danger/80">
            Nothing was lost — your answers are saved on this device.
          </p>
          {retryable && (
            <Button
              variant="outline"
              className="min-h-[44px] w-full text-sm"
              disabled={loading}
              onClick={handleGenerate}
            >
              {loading ? "Retrying..." : "Retry"}
            </Button>
          )}
        </div>
      )}

      <div className="rounded-md border border-muted px-4 py-3 text-sm text-muted-foreground">
        A test week calibrates your week-1 prescriptions with precise baselines. Or start immediately and self-report.
      </div>

      <div className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          className="text-sm px-3 py-2"
          onClick={() => router.push("/onboarding/trips")}
          disabled={loading}
        >
          Back
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="min-h-[44px] text-sm px-3"
            disabled={loading || profileProblems.length > 0}
            onClick={handleGenerate}
          >
            {loading ? "Generating..." : "Start training now"}
          </Button>
          <Button
            className="min-h-[44px] text-sm px-3"
            disabled={loading || profileProblems.length > 0}
            onClick={handleTestWeek}
          >
            {loading ? "Generating..." : "Run a test week first"}
          </Button>
        </div>
      </div>
    </div>
  );
}
