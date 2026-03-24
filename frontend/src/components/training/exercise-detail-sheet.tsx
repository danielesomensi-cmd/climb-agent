"use client";

import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Badge } from "@/components/ui/badge";
import { Film } from "lucide-react";

interface ExerciseDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Raw resolved exercise instance from the week plan API */
  exercise: Record<string, unknown> | null;
}

/** Format seconds → "2:00" or "45s" */
function formatRest(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? (s > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${m}:00`) : `${s}s`;
}

/** Format category slug → readable label */
function formatCategory(cat: string): string {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Build prescription lines from raw exercise data */
function buildPrescription(ex: Record<string, unknown>): string[] {
  const p = (ex.prescription ?? {}) as Record<string, unknown>;
  const lines: string[] = [];

  const sets = p.sets as number | undefined;
  const reps = p.reps as string | number | undefined;
  const workSec = (p.work_seconds ?? p.hang_seconds) as number | undefined;
  const restReps = p.rest_between_reps_seconds as number | undefined;
  const restSets = (p.rest_between_sets_seconds ?? p.rest_s) as number | undefined;
  const loadKg = p.load_kg as number | undefined;
  const tempo = p.tempo as string | undefined;
  const intensityPct = p.intensity_pct_of_total_load as number | undefined;

  // Main scheme: sets × reps × duration
  if (sets && reps && workSec) {
    const work = workSec >= 60 ? `${Math.round(workSec / 60)} min` : `${workSec}s`;
    lines.push(`${sets} × ${reps} × ${work}`);
  } else if (sets && reps) {
    lines.push(`${sets} × ${reps}`);
  } else if (sets && workSec) {
    const work = workSec >= 60 ? `${Math.round(workSec / 60)} min` : `${workSec}s`;
    lines.push(`${sets} × ${work}`);
  } else if (workSec) {
    const work = workSec >= 60 ? `${Math.round(workSec / 60)} min` : `${workSec}s`;
    lines.push(work);
  } else if (sets && !reps) {
    lines.push(`${sets} sets`);
  } else if (reps) {
    lines.push(String(reps));
  }

  // Rest
  if (restReps) lines.push(`Rest between reps: ${formatRest(restReps)}`);
  if (restSets) {
    const label = restReps ? "Set rest" : "Rest";
    lines.push(`${label}: ${formatRest(restSets)}`);
  }

  // Load
  if (loadKg != null) {
    lines.push(loadKg > 0 ? `Load: ${loadKg} kg` : "Load: bodyweight");
  }

  // Intensity
  if (intensityPct != null) {
    lines.push(`Intensity: ${Math.round(intensityPct * 100)}%`);
  }

  // Tempo
  if (tempo) lines.push(`Tempo: ${tempo}`);

  return lines;
}

/** Build suggested load/grade section */
function buildSuggested(ex: Record<string, unknown>): string[] {
  const s = (ex.suggested ?? {}) as Record<string, unknown>;
  const lines: string[] = [];
  const isUnilateral = ex.unilateral === true;

  if (isUnilateral) {
    const rh = s.right_hand as Record<string, unknown> | undefined;
    const lh = s.left_hand as Record<string, unknown> | undefined;
    if (rh?.suggested_external_load_kg != null || lh?.suggested_external_load_kg != null) {
      const r = rh?.suggested_external_load_kg as number | undefined;
      const l = lh?.suggested_external_load_kg as number | undefined;
      lines.push(`Left: +${l ?? "?"} kg  /  Right: +${r ?? "?"} kg`);
    }
  } else {
    if (s.suggested_external_load_kg != null) {
      let line = `Suggested: +${s.suggested_external_load_kg} kg`;
      if (s.suggested_total_load_kg != null) {
        line += ` (total: ${s.suggested_total_load_kg} kg)`;
      }
      if (s.load_source === "estimated") line += " (est.)";
      lines.push(line);
    } else if (s.suggested_total_load_kg != null) {
      let line = `Suggested total: ${s.suggested_total_load_kg} kg`;
      if (s.load_source === "estimated") line += " (est.)";
      lines.push(line);
    }
  }

  if (s.suggested_rep_scheme) {
    lines.push(`Rep scheme: ${s.suggested_rep_scheme}`);
  }

  // Grade
  if (s.suggested_grade || s.grade) {
    let line = `Grade: ${s.suggested_grade ?? s.grade}`;
    if (s.surface) line += ` on ${s.surface}`;
    lines.push(line);
  }

  // Boulder target
  const bt = s.suggested_boulder_target as Record<string, unknown> | undefined;
  if (bt?.target_grade) {
    let line = `Target: ${bt.target_grade}`;
    if (bt.surface_selected) line += ` on ${bt.surface_selected}`;
    if (bt.intensity_label) line += ` (${bt.intensity_label})`;
    lines.push(line);
  }

  // Load warning
  if (s.load_warning) {
    lines.push(String(s.load_warning));
  }

  return lines;
}

/** Get equipment list from exercise attributes */
function getEquipment(ex: Record<string, unknown>): string[] {
  const attrs = ex.attributes as Record<string, unknown> | undefined;
  const eq = attrs?.equipment_required as string[] | undefined;
  const eqAny = attrs?.equipment_required_any as string[] | undefined;
  const result: string[] = [];
  if (eq?.length) result.push(...eq);
  if (eqAny?.length) result.push(...eqAny);
  return result;
}

const LIMITATION_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  severe: { bg: "bg-red-500/10", text: "text-red-400", label: "Severe" },
  active: { bg: "bg-orange-500/10", text: "text-orange-400", label: "Active" },
  monitor: { bg: "bg-yellow-500/10", text: "text-yellow-400", label: "Monitor" },
};

export function ExerciseDetailSheet({ open, onOpenChange, exercise }: ExerciseDetailSheetProps) {
  if (!exercise) return null;

  const name = (exercise.name as string) ?? (exercise.exercise_id as string ?? "").replace(/_/g, " ");
  const category = exercise.category as string | undefined;
  const cues = (exercise.cues ?? []) as string[];
  const videoUrl = exercise.video_url as string | undefined;
  const prescriptionObj = (exercise.prescription ?? {}) as Record<string, unknown>;
  const notes = prescriptionObj.notes as string | undefined;

  const prescriptionLines = buildPrescription(exercise);
  const suggestedLines = buildSuggested(exercise);
  const equipment = getEquipment(exercise);

  // Limitation warning
  const limitationWarning = exercise.limitation_warning as string | undefined;
  const limitationZone = exercise.limitation_zone as string | undefined;
  const limitStyle = limitationWarning ? LIMITATION_STYLES[limitationWarning] : null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader className="text-left pb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <DrawerTitle className="text-base">{name}</DrawerTitle>
            {category && (
              <Badge variant="secondary" className="text-[10px]">
                {formatCategory(category)}
              </Badge>
            )}
          </div>
        </DrawerHeader>

        <div className="px-4 pb-6 space-y-4 overflow-y-auto">
          {/* Limitation warning */}
          {limitStyle && limitationZone && (
            <div className={`rounded-md px-3 py-2 ${limitStyle.bg}`}>
              <p className={`text-xs font-medium ${limitStyle.text}`}>
                {limitStyle.label}: {formatCategory(limitationZone)}
              </p>
            </div>
          )}

          {/* Prescription */}
          {prescriptionLines.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Prescription</p>
              {prescriptionLines.map((line, i) => (
                <p key={i} className={`text-sm ${i === 0 ? "font-medium" : "text-muted-foreground"}`}>
                  {line}
                </p>
              ))}
            </div>
          )}

          {/* Suggested load / grade */}
          {suggestedLines.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Suggested</p>
              {suggestedLines.map((line, i) => (
                <p key={i} className="text-sm text-muted-foreground">
                  {line}
                </p>
              ))}
            </div>
          )}

          {/* Notes */}
          {notes && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Notes</p>
              <p className="text-sm text-muted-foreground">{notes}</p>
            </div>
          )}

          {/* Technique cues */}
          {cues.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Cues</p>
              <ul className="space-y-0.5">
                {cues.map((cue, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-1.5">
                    <span className="text-primary mt-1 shrink-0">•</span>
                    <span>{cue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Equipment */}
          {equipment.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Equipment</p>
              <div className="flex flex-wrap gap-1.5">
                {equipment.map((eq) => (
                  <Badge key={eq} variant="outline" className="text-xs">
                    {formatCategory(eq)}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Video */}
          {videoUrl && (
            <a
              href={videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-primary hover:underline"
            >
              <Film className="size-3.5" />
              Watch video
            </a>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
