"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RadarChart } from "@/components/onboarding/radar-chart";
import { InAppBrowserBanner } from "@/components/install/in-app-browser-banner";
import { seedDraftFromAssessment } from "@/components/onboarding/onboarding-context";
import {
  computePublicAssessment,
  type PublicAssessmentResult,
} from "@/lib/api";
import { BOULDER_GRADE_OPTIONS, LEAD_GRADE_OPTIONS } from "@/lib/gradeUtils";
import { captureUtmOnMount, trackEvent } from "@/lib/analytics";
import { useEffect } from "react";

/**
 * A262 — the public 5-axis assessment.
 *
 * Everything else in the app is behind an account. This page exists to give
 * something away first: a cold visitor answers six questions and gets the same
 * profile the engine computes internally, with nothing stored and no sign-up.
 * That is what makes the link postable somewhere like r/climbharder without it
 * reading as an ad.
 *
 * The answers are seeded into the wizard's anonymous draft on the CTA, so
 * someone who continues does not retype what they just told us.
 */

type Discipline = "lead" | "boulder";

/** Mirrors the backend's WEAKNESS_OPTIONS_* — kept short on purpose: this is a
 *  six-question form, not the wizard's dedicated step. */
const WEAKNESSES: { id: string; label: string }[] = [
  { id: "fingers_give_out", label: "My fingers give out" },
  { id: "cant_hold_hard_moves", label: "Can't hold hard moves" },
  { id: "pump_too_early", label: "I pump out too early" },
  { id: "technique_errors", label: "Technique errors" },
  { id: "poor_body_tension", label: "Poor body tension" },
  { id: "weak_on_slopers", label: "Weak on slopers" },
  { id: "cant_read_routes", label: "Can't read routes" },
  { id: "poor_dynamic_movement", label: "Poor dynamic movement" },
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? (
        <span className="block text-xs text-muted-foreground">{hint}</span>
      ) : null}
      {children}
    </label>
  );
}

const SELECT_CLASS =
  "min-h-[44px] w-full rounded-md border border-input bg-background px-3 text-base text-foreground";

export default function PublicAssessmentPage() {
  const router = useRouter();
  const [discipline, setDiscipline] = useState<Discipline>("lead");
  const [currentGrade, setCurrentGrade] = useState("");
  const [targetGrade, setTargetGrade] = useState("");
  const [maxRp, setMaxRp] = useState("");
  const [maxOs, setMaxOs] = useState("");
  const [years, setYears] = useState("3");
  const [weakness, setWeakness] = useState("");
  const [result, setResult] = useState<PublicAssessmentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureUtmOnMount();
    trackEvent("public_assessment_view");
  }, []);

  const grades = discipline === "lead" ? LEAD_GRADE_OPTIONS : BOULDER_GRADE_OPTIONS;

  const complete =
    currentGrade !== "" && targetGrade !== "" && maxRp !== "" && maxOs !== "";

  const seed = useMemo(
    () => ({
      discipline,
      current_grade: currentGrade,
      target_grade: targetGrade,
      max_rp: maxRp,
      max_os: maxOs,
      climbing_years: Number(years) || 0,
      primary_weakness: weakness || null,
    }),
    [discipline, currentGrade, targetGrade, maxRp, maxOs, years, weakness],
  );

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await computePublicAssessment(seed);
      setResult(res);
      trackEvent("public_assessment_completed", {
        discipline,
        weakest_axis: res.weakest_axis,
      });
    } catch (e) {
      // The backend rejects what it cannot score honestly (unknown grade,
      // onsight above redpoint) — surface its reason rather than a generic
      // failure, because in every case it tells the user what to fix.
      setError(
        e instanceof Error ? e.message : "Could not compute your profile.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    const axisScore = result.profile[result.weakest_axis];
    return (
      <div className="mx-auto max-w-lg space-y-6 px-4 pb-16 pt-8">
        <InAppBrowserBanner />
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Your profile</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Five axes, scored against the benchmarks for {result.target_grade_lead}.
          </p>
        </div>

        <Card>
          <CardContent className="flex justify-center pt-6">
            <RadarChart
              profile={result.profile}
              discipline={discipline}
              targetGrade={result.target_grade_lead}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Weakest link: {result.weakest_axis_label}
            </CardTitle>
            <CardDescription>
              It scores {axisScore}/100 against your target. On a periodized
              plan this is what gets trained first — progress on your weakest
              axis moves your grade more than more of what you are already good
              at.
            </CardDescription>
          </CardHeader>
        </Card>

        {result.estimated ? (
          <p className="text-xs text-muted-foreground">
            This is an estimate, not a measurement: it is derived from the
            grades you reported and your own assessment of your weakness. Add
            hangboard and pull-up test numbers during onboarding and the finger
            and pulling axes become measured instead of inferred.
          </p>
        ) : null}

        <div className="space-y-3">
          <Button
            className="min-h-[52px] w-full text-base"
            onClick={() => {
              // Carry the six answers into the wizard's anonymous draft so the
              // visitor does not retype them (A256 adopts it at sign-in).
              seedDraftFromAssessment(seed);
              trackEvent("public_assessment_cta");
              router.push("/onboarding/profile");
            }}
          >
            Build my training plan
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Your answers are carried over — no need to enter them again.
          </p>
          <Button
            variant="ghost"
            className="min-h-[44px] w-full"
            onClick={() => setResult(null)}
          >
            Change my answers
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 px-4 pb-16 pt-8">
      <InAppBrowserBanner />
      <div>
        <h1 className="text-2xl font-semibold text-foreground">
          Where are you actually weak?
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Six questions, no account. You get the same five-axis profile the
          planner uses to decide what you should train.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-5 pt-6">
          <Field label="Discipline">
            <div className="grid grid-cols-2 gap-3">
              {(["lead", "boulder"] as const).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => {
                    // Grades belong to a scale; keeping them across a switch
                    // would send Font values to the lead branch.
                    setDiscipline(d);
                    setCurrentGrade("");
                    setTargetGrade("");
                    setMaxRp("");
                    setMaxOs("");
                  }}
                  className={`min-h-[44px] rounded-lg border px-4 text-base font-semibold ${
                    discipline === d
                      ? "border-primary ring-2 ring-primary/30 text-foreground"
                      : "border-muted text-muted-foreground"
                  }`}
                >
                  {d === "lead" ? "Lead / sport" : "Boulder"}
                </button>
              ))}
            </div>
          </Field>

          <Field
            label="Hardest grade you've redpointed"
            hint={discipline === "boulder" ? "Fontainebleau scale" : "French scale"}
          >
            <select
              className={SELECT_CLASS}
              value={maxRp}
              onChange={(e) => setMaxRp(e.target.value)}
            >
              <option value="">Select…</option>
              {grades.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field
            label={discipline === "boulder" ? "Hardest flash" : "Hardest onsight"}
            hint="The gap between this and your redpoint is what reveals technique and power endurance."
          >
            <select
              className={SELECT_CLASS}
              value={maxOs}
              onChange={(e) => setMaxOs(e.target.value)}
            >
              <option value="">Select…</option>
              {grades.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field label="Grade you're operating at now">
            <select
              className={SELECT_CLASS}
              value={currentGrade}
              onChange={(e) => setCurrentGrade(e.target.value)}
            >
              <option value="">Select…</option>
              {grades.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field label="Grade you're chasing">
            <select
              className={SELECT_CLASS}
              value={targetGrade}
              onChange={(e) => setTargetGrade(e.target.value)}
            >
              <option value="">Select…</option>
              {grades.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field label="Years climbing">
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={70}
              className={SELECT_CLASS}
              value={years}
              onChange={(e) => setYears(e.target.value)}
            />
          </Field>

          <Field label="What holds you back most?" hint="Optional">
            <select
              className={SELECT_CLASS}
              value={weakness}
              onChange={(e) => setWeakness(e.target.value)}
            >
              <option value="">Prefer not to say</option>
              {WEAKNESSES.map((w) => (
                <option key={w.id} value={w.id}>{w.label}</option>
              ))}
            </select>
          </Field>
        </CardContent>
      </Card>

      {error ? (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-foreground">
          {error}
        </p>
      ) : null}

      <Button
        className="min-h-[52px] w-full text-base"
        disabled={!complete || busy}
        onClick={submit}
      >
        {busy ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : null}
        See my profile
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        Nothing is saved. No account, no email.
      </p>
    </div>
  );
}
