"use client";

/**
 * A292 (R6b) — "your log says your onsight is higher" card.
 *
 * Shown only when GET /api/assessment/grade-evidence proposes a grade. Asks,
 * route by route, whether each send was onsight, flash or worked; the server
 * writes the grade only on confirm, and never rewrites the outdoor log.
 */
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiErrorDetail, confirmGrade, getGradeEvidence } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import {
  initialAnswers,
  supportedGrade,
  type EvidenceStyle,
  type GradeEvidence,
} from "@/lib/grade-evidence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const STYLE_LABELS: Array<[EvidenceStyle, string]> = [
  ["onsight", "Onsight"],
  ["flash", "Flash"],
  ["worked", "Worked"],
];

export function OnsightEvidenceCard() {
  const [done, setDone] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: queryKeys.gradeEvidence,
    queryFn: getGradeEvidence,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  if (done) {
    return (
      <Card className="border-primary/40">
        <CardContent className="py-4 text-sm">{done}</CardContent>
      </Card>
    );
  }
  if (!data || !data.proposed || data.routes.length === 0) return null;
  // Remount on a new proposal so the answers start from the log again.
  return (
    <EvidenceBody key={`${data.proposed}|${data.routes.length}`} evidence={data} onDone={setDone} />
  );
}

function EvidenceBody({
  evidence,
  onDone,
}: {
  evidence: GradeEvidence;
  onDone: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState(() => initialAnswers(evidence.routes));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported = useMemo(
    () => supportedGrade(evidence.routes, answers, evidence.min_routes),
    [evidence, answers],
  );
  const allAnswered = evidence.routes.every((r) => answers[r.key]);

  async function submit(decision: "confirm" | "dismiss") {
    setBusy(true);
    setError(null);
    try {
      const routes = evidence.routes
        .filter((r) => answers[r.key])
        .map((r) => ({ key: r.key, style: answers[r.key] as EvidenceStyle }));
      const res = await confirmGrade({ decision, routes });
      onDone(
        decision === "confirm"
          ? `Onsight updated to ${res.grade}.`
          : "Got it — we won't ask about this grade again.",
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.gradeEvidence }),
        queryClient.invalidateQueries({ queryKey: queryKeys.state }),
        queryClient.invalidateQueries({ queryKey: queryKeys.weekAll }),
      ]);
    } catch (err) {
      setError(apiErrorDetail(err, "Could not save. Try again."));
      setBusy(false);
    }
  }

  return (
    <Card className="border-primary/40" data-testid="onsight-evidence-card">
      <CardHeader>
        <CardTitle className="text-base">
          Your log says onsight {evidence.proposed}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Declared: {evidence.current ?? "—"}. These routes went in one try at their first
          appearance in your log. Were they really onsight?
          {evidence.all_in_trip && " All of them are from a trip — be honest about beta."}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {evidence.routes.map((r) => (
          <div key={r.key} className="space-y-1">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="min-w-0 truncate">
                <span className="font-medium">{r.name}</span>{" "}
                <span className="text-muted-foreground">{r.grade}</span>
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {r.spot_name} · {r.date}
              </span>
            </div>
            <div className="flex gap-1" role="radiogroup" aria-label={`Style for ${r.name}`}>
              {STYLE_LABELS.map(([style, label]) => (
                <Button
                  key={style}
                  type="button"
                  size="sm"
                  variant={answers[r.key] === style ? "default" : "outline"}
                  className="h-7 flex-1 text-xs"
                  role="radio"
                  aria-checked={answers[r.key] === style}
                  onClick={() => setAnswers((a) => ({ ...a, [r.key]: style }))}
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>
        ))}
        <p className="text-xs text-muted-foreground">
          {supported
            ? `Your answers support onsight ${supported}.`
            : `Needs ${evidence.min_routes} onsight or flash routes, on two days or at two crags.`}
        </p>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <div className="flex gap-2">
          <Button
            size="sm"
            className="flex-1"
            disabled={busy || !allAnswered || !supported}
            onClick={() => submit("confirm")}
          >
            {busy ? "Saving…" : `Confirm ${supported ?? ""}`.trim()}
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => submit("dismiss")}>
            Not my onsight
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
