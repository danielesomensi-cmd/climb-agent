"use client";

import { Target, BarChart3, Lightbulb } from "lucide-react";

const GOAL_LABELS: Record<string, string> = {
  finger_max_strength: "Finger max strength",
  finger_strength: "Finger strength",
  finger_strength_endurance: "Finger endurance",
  finger_aerobic_endurance: "Finger aerobic base",
  climbing_movement: "Climbing movement",
  power: "Power & contact strength",
  power_endurance: "Power endurance",
  pulling_strength: "Pulling strength",
  core_tension: "Core stability",
  joint_health: "Joint health & prehab",
  aerobic_capacity: "Aerobic capacity",
  technique: "Technique",
  technique_footwork: "Technique",
  technique_boulder: "Technique",
  flexibility: "Flexibility",
  regeneration: "Active recovery",
  climbing_routes: "Route climbing",
  contact_strength: "Contact strength",
  limit_projecting: "Limit projecting",
  route_projecting: "Route projecting",
  volume_climbing: "Volume climbing",
  strength_general: "General strength",
  core: "Core stability",
  prehab_shoulder: "Joint health & prehab",
  handstand_skill: "Handstand skill",
};

const PHASE_CONTEXT: Record<string, string> = {
  base: "Base phase — building your aerobic engine",
  strength_power: "Strength & Power — building raw force for harder moves",
  power_endurance: "Power Endurance — sustaining hard moves back to back",
  performance: "Performance — peak phase, time to send projects",
  deload: "Recovery — let your body absorb the training",
};

interface SessionContextCardProps {
  /** resolved_session object from API */
  resolvedSession?: Record<string, unknown>;
  /** phase_id from the week plan profile snapshot */
  phaseId?: string;
  /** session_load_score from the resolved session */
  loadScore?: number;
}

export function SessionContextCard({ resolvedSession, phaseId, loadScore }: SessionContextCardProps) {
  if (!resolvedSession) return null;

  // Line 1 — Focus: extract intent
  const session = resolvedSession.session as Record<string, unknown> | undefined;
  const intent = (session?.intent ?? resolvedSession.intent) as Record<string, unknown> | undefined;
  const primaryGoal = intent?.primary_goal as string | undefined;
  const secondaryGoals = (intent?.secondary_goals ?? []) as string[];

  let focusLine: string | null = null;
  if (primaryGoal && GOAL_LABELS[primaryGoal]) {
    const parts = [GOAL_LABELS[primaryGoal]];
    if (secondaryGoals.length > 0 && GOAL_LABELS[secondaryGoals[0]]) {
      parts.push(GOAL_LABELS[secondaryGoals[0]]);
    }
    focusLine = parts.join(", ");
  }

  // Line 2 — Phase context
  const phaseLine = phaseId ? PHASE_CONTEXT[phaseId] ?? null : null;

  // Line 3 — Monitoring tip
  let tipLine: string | null = null;

  // Check progression targets on primary module exercises
  const instances = (resolvedSession.exercise_instances ?? []) as Array<Record<string, unknown>>;
  for (const inst of instances) {
    const suggested = (inst.suggested ?? {}) as Record<string, unknown>;
    const totalLoad = suggested.suggested_total_load_kg as number | undefined;
    const externalLoad = suggested.suggested_external_load_kg as number | undefined;
    const grade = suggested.suggested_grade as string | undefined;
    const boulderTarget = (suggested.suggested_boulder_target ?? {}) as Record<string, unknown>;
    const targetGrade = boulderTarget.target_grade as string | undefined;

    if (totalLoad != null) {
      tipLine = `Target: ${totalLoad}kg total`;
      break;
    }
    if (externalLoad != null && externalLoad > 0) {
      tipLine = `Target: +${externalLoad}kg`;
      break;
    }
    if (grade ?? targetGrade) {
      tipLine = `Target grade: ${grade ?? targetGrade}`;
      break;
    }
  }

  if (!tipLine && loadScore != null) {
    if (loadScore >= 70) {
      tipLine = "High intensity session — prioritise rest tomorrow";
    } else if (loadScore <= 30) {
      tipLine = "Light session — focus on quality and control";
    }
  }

  // If deload phase, override tip
  if (phaseId === "deload" && !tipLine) {
    tipLine = "Easy effort — active recovery only";
  }

  // Don't render if we have nothing useful
  if (!focusLine && !phaseLine) return null;

  return (
    <div className="rounded-md bg-slate-800/50 px-3 py-2 space-y-0.5">
      {focusLine && (
        <div className="flex items-center gap-1.5 text-xs text-slate-200">
          <Target className="size-3 shrink-0 text-amber-400" />
          <span>Focus: {focusLine}</span>
        </div>
      )}
      {phaseLine && (
        <div className="flex items-center gap-1.5 text-xs text-slate-300/80">
          <BarChart3 className="size-3 shrink-0 text-teal-400" />
          <span>{phaseLine}</span>
        </div>
      )}
      {tipLine && (
        <div className="flex items-center gap-1.5 text-xs text-slate-300/70">
          <Lightbulb className="size-3 shrink-0 text-yellow-400" />
          <span>{tipLine}</span>
        </div>
      )}
    </div>
  );
}
