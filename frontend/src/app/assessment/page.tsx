"use client";

import { useEffect, useMemo, useState } from "react";
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
import {
  BOULDER_GRADE_OPTIONS,
  LEAD_GRADE_OPTIONS,
  V_SCALE_GRADES,
  YDS_GRADE_OPTIONS,
  vScaleToFont,
  ydsToFrench,
} from "@/lib/gradeUtils";
import { captureUtmOnMount, trackEvent } from "@/lib/analytics";

/**
 * A262/A263 — the public 5-axis assessment.
 *
 * Everything else in the app is behind an account. This page gives something
 * away first: six questions, the same profile the engine computes internally,
 * nothing stored and no sign-up. That is what makes the link postable somewhere
 * like r/climbharder without it reading as an ad.
 *
 * A263 fixed three things that made the first version feel thin:
 *
 * - **Grade scale is selectable.** The audience is largely American; a
 *   French/Font-only picker is unusable for half of it.
 * - **"Operating at now" was unreadable.** It means the grade you climb
 *   repeatedly, as distinct from your best ever — now said that way.
 * - **It asked nothing about fingers** while showing finger strength as the
 *   first axis. A climber who trains knows their max hang; not asking left the
 *   most scrutinised number on the page as pure inference.
 */

type Discipline = "lead" | "boulder";
/** native = French / Font (the engine's own convention), alt = YDS / V-scale. */
type Scale = "native" | "alt";

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

const SELECT_CLASS =
  "min-h-[44px] w-full rounded-md border border-input bg-background px-3 text-base text-foreground";

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

export default function PublicAssessmentPage() {
  const router = useRouter();
  const [discipline, setDiscipline] = useState<Discipline>("lead");
  const [scale, setScale] = useState<Scale>("native");
  const [currentGrade, setCurrentGrade] = useState("");
  const [targetGrade, setTargetGrade] = useState("");
  const [maxRp, setMaxRp] = useState("");
  const [maxOs, setMaxOs] = useState("");
  const [years, setYears] = useState("3");
  const [weakness, setWeakness] = useState("");
  const [showNumbers, setShowNumbers] = useState(false);
  const [bodyweight, setBodyweight] = useState("");
  const [maxHang, setMaxHang] = useState("");
  const [pullup, setPullup] = useState("");
  const [result, setResult] = useState<PublicAssessmentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureUtmOnMount();
    trackEvent("public_assessment_view");
  }, []);

  const isBoulder = discipline === "boulder";

  const gradeOptions = useMemo(() => {
    if (isBoulder) return scale === "native" ? BOULDER_GRADE_OPTIONS : V_SCALE_GRADES;
    return scale === "native" ? LEAD_GRADE_OPTIONS : YDS_GRADE_OPTIONS;
  }, [isBoulder, scale]);

  /** To the engine's convention (Font for boulder, French for lead) before
   *  anything leaves this page — the same rule the rest of the app follows. */
  const toEngine = useMemo(() => {
    if (scale === "native") return (g: string) => g;
    return isBoulder ? vScaleToFont : ydsToFrench;
  }, [scale, isBoulder]);

  const complete =
    currentGrade !== "" && targetGrade !== "" && maxRp !== "" && maxOs !== "";

  const seed = useMemo(
    () => ({
      discipline,
      current_grade: toEngine(currentGrade),
      target_grade: toEngine(targetGrade),
      max_rp: toEngine(maxRp),
      max_os: toEngine(maxOs),
      climbing_years: Number(years) || 0,
      primary_weakness: weakness || null,
    }),
    [discipline, toEngine, currentGrade, targetGrade, maxRp, maxOs, years, weakness],
  );

  function resetGrades() {
    setCurrentGrade("");
    setTargetGrade("");
    setMaxRp("");
    setMaxOs("");
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await computePublicAssessment({
        ...seed,
        bodyweight_kg: bodyweight ? Number(bodyweight) : null,
        max_hang_added_kg: maxHang !== "" ? Number(maxHang) : null,
        weighted_pullup_added_kg: pullup !== "" ? Number(pullup) : null,
      });
      setResult(res);
      trackEvent("public_assessment_completed", {
        discipline,
        weakest_axis: res.weakest_axis,
        measured: res.measured_axes.length,
      });
    } catch (e) {
      // The backend rejects what it cannot score honestly (unknown grade,
      // onsight above redpoint, numbers without a bodyweight) — surface its
      // reason, because in every case it tells the user what to fix.
      setError(e instanceof Error ? e.message : "Could not compute your profile.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    const axisScore = result.profile[result.weakest_axis];
    const measured = result.measured_axes.length;
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
              It scores {axisScore}/100 against your target. On a periodized plan
              this is what gets trained first — progress on your weakest axis
              moves your grade more than more of what you are already good at.
            </CardDescription>
          </CardHeader>
        </Card>

        <p className="text-xs text-muted-foreground">
          {measured > 0 ? (
            <>
              {measured === 1 ? "One axis is" : `${measured} axes are`} computed
              from the numbers you entered, against your bodyweight. The rest are
              derived from your declared grades and your own read on your
              weakness — useful, but not a measurement.
            </>
          ) : (
            <>
              This is an estimate, not a measurement: every axis is derived from
              the grades you reported and your own read on your weakness. Add a
              max hang and a weighted pull-up and two of them become measured.
            </>
          )}
        </p>

        <div className="space-y-3">
          <Button
            className="min-h-[52px] w-full text-base"
            onClick={() => {
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
        {/* B318 — this promise also sits under the submit button, but that is
            below the fold on a 390px phone: it reassures at the moment the user
            has already decided, not at the moment they decide. */}
        <p className="mt-2 text-xs text-muted-foreground">
          Nothing is saved. No account, no email.
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
                    // would send Font values into the lead branch.
                    setDiscipline(d);
                    setScale("native");
                    resetGrades();
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

          <Field label="Grade scale">
            <div className="grid grid-cols-2 gap-3">
              {(["native", "alt"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setScale(s);
                    resetGrades();
                  }}
                  className={`min-h-[44px] rounded-lg border px-4 text-sm font-semibold ${
                    scale === s
                      ? "border-primary ring-2 ring-primary/30 text-foreground"
                      : "border-muted text-muted-foreground"
                  }`}
                >
                  {isBoulder
                    ? s === "native"
                      ? "Font (7A)"
                      : "V-scale (V6)"
                    : s === "native"
                      ? "French (7a)"
                      : "YDS (5.11d)"}
                </button>
              ))}
            </div>
          </Field>

          <Field
            label="Hardest grade you've ever sent"
            hint="Redpoint — worked over multiple attempts."
          >
            <select
              className={SELECT_CLASS}
              value={maxRp}
              onChange={(e) => setMaxRp(e.target.value)}
            >
              <option value="">Select…</option>
              {gradeOptions.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field
            label={isBoulder ? "Hardest flash" : "Hardest onsight"}
            hint="First try, no prior beta. The gap between this and your redpoint is what reveals technique and power endurance."
          >
            <select
              className={SELECT_CLASS}
              value={maxOs}
              onChange={(e) => setMaxOs(e.target.value)}
            >
              <option value="">Select…</option>
              {gradeOptions.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field
            label="Grade you climb regularly"
            hint="What you send on a normal day — not your best ever. Usually a couple of grades below your redpoint."
          >
            <select
              className={SELECT_CLASS}
              value={currentGrade}
              onChange={(e) => setCurrentGrade(e.target.value)}
            >
              <option value="">Select…</option>
              {gradeOptions.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </Field>

          <Field label="Grade you're chasing" hint="Your next real target.">
            <select
              className={SELECT_CLASS}
              value={targetGrade}
              onChange={(e) => setTargetGrade(e.target.value)}
            >
              <option value="">Select…</option>
              {gradeOptions.map((g) => (
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

      {/* A263 — the numbers block. Collapsed by default so the six-question
          promise holds, but prominent enough that anyone who trains and knows
          their max hang will open it: those two values are what turn the finger
          and pulling axes from inference into measurement. */}
      <Card>
        <CardContent className="pt-6">
          {showNumbers ? (
            <div className="space-y-5">
              <div>
                <p className="text-sm font-medium text-foreground">
                  Your test numbers
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Optional — but with these, finger strength and pulling stop
                  being inferred from your grades and get measured against
                  bodyweight, the way the research benchmarks them.
                </p>
              </div>

              <Field
                label="Bodyweight (kg)"
                hint="Required to score the numbers below."
              >
                <input
                  type="number"
                  inputMode="decimal"
                  className={SELECT_CLASS}
                  value={bodyweight}
                  onChange={(e) => setBodyweight(e.target.value)}
                />
              </Field>

              <Field
                label="Max hang — 20 mm edge, 7 s, added weight (kg)"
                hint="Half crimp. Negative if you use assistance (e.g. -8)."
              >
                <input
                  type="number"
                  inputMode="decimal"
                  className={SELECT_CLASS}
                  value={maxHang}
                  onChange={(e) => setMaxHang(e.target.value)}
                />
              </Field>

              <Field
                label="Weighted pull-up 1RM — added weight (kg)"
                hint="Negative if assisted."
              >
                <input
                  type="number"
                  inputMode="decimal"
                  className={SELECT_CLASS}
                  value={pullup}
                  onChange={(e) => setPullup(e.target.value)}
                />
              </Field>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                setShowNumbers(true);
                trackEvent("public_assessment_open_numbers");
              }}
              className="w-full text-left"
            >
              <p className="text-sm font-medium text-foreground">
                Know your max hang? Add your numbers →
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Optional. Turns finger strength and pulling from estimated into
                measured.
              </p>
            </button>
          )}
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
