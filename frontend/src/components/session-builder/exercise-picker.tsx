"use client";

import { useState, useDeferredValue } from "react";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useBuilderExercises } from "@/lib/hooks/queries";
import type { BuilderExercise, CustomSessionExercise } from "@/lib/types";
import { Plus, Search, X } from "lucide-react";

const DOMAIN_CHIPS: { label: string; domains: string[] }[] = [
  { label: "All", domains: [] },
  { label: "Finger", domains: ["finger_strength", "finger_max_strength", "finger_strength_endurance", "finger_aerobic_endurance"] },
  { label: "Pulling", domains: ["strength_pulling"] },
  { label: "Core", domains: ["core"] },
  { label: "Power", domains: ["power", "contact_strength"] },
  { label: "Endurance", domains: ["aerobic_capacity", "anaerobic_capacity", "power_endurance"] },
  { label: "Technique", domains: ["technique_boulder", "technique_lead", "technique_footwork", "technique_body_position", "technique_constraint", "technique_movement"] },
  { label: "Prehab", domains: ["prehab_elbow", "prehab_finger", "prehab_shoulder", "prehab_wrist"] },
  { label: "Mobility", domains: ["mobility", "flexibility"] },
  { label: "General", domains: ["strength_general"] },
];

function exerciseToDefaults(ex: BuilderExercise): CustomSessionExercise {
  const d = ex.prescription_defaults;
  return {
    exercise_id: ex.id,
    sets: d.sets ?? 1,
    reps: d.reps ?? null,
    work_seconds: d.work_seconds ?? null,
    rest_between_sets_seconds: d.rest_between_sets_seconds ?? null,
    rest_between_reps_seconds: d.rest_between_reps_seconds ?? null,
    // A242: prefill the user's remembered load (0 when none) — never invented.
    load_kg: ex.proposal?.load_kg ?? 0,
    // B324: laterality is a catalog property. Carried here only so the builder
    // can label it "per side" pre-save; the server re-derives it on persist.
    alt_sides: ex.alt_sides === true,
    notes: "",
  };
}

/** Compact relative age, e.g. "today", "3 days ago", "5 months ago". */
function formatAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const then = new Date(dateStr + "T00:00:00");
  if (Number.isNaN(then.getTime())) return "";
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) {
    const w = Math.floor(days / 7);
    return `${w} week${w > 1 ? "s" : ""} ago`;
  }
  if (days < 365) {
    const m = Math.floor(days / 30);
    return `${m} month${m > 1 ? "s" : ""} ago`;
  }
  const y = Math.floor(days / 365);
  return `${y} year${y > 1 ? "s" : ""} ago`;
}

/** "Last time: 40 kg · 3 months ago" — remembered load/effort memory, or null. */
function lastTimeLabel(ex: BuilderExercise): string | null {
  const last = ex.proposal?.last_logged;
  if (!last) return null;
  const ago = formatAgo(last.date);
  const head =
    last.load_kg != null && last.load_kg > 0
      ? `${last.load_kg} kg`
      : last.feedback_label
        ? last.feedback_label.replace(/_/g, " ")
        : "logged";
  return ago ? `Last time: ${head} · ${ago}` : `Last time: ${head}`;
}

function formatDefaults(ex: BuilderExercise): string {
  const d = ex.prescription_defaults;
  const parts: string[] = [];
  if (d.sets) {
    if (d.reps) parts.push(`${d.sets}\u00d7${d.reps}`);
    else if (d.work_seconds) parts.push(`${d.sets}\u00d7${d.work_seconds}s`);
    else parts.push(`${d.sets} sets`);
  }
  if (d.rest_between_sets_seconds) parts.push(`Rest ${d.rest_between_sets_seconds}s`);
  return parts.join(" \u00b7 ");
}

interface ExercisePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (exercise: CustomSessionExercise, name: string) => void;
  addedIds: Set<string>;
}

export function ExercisePicker({ open, onOpenChange, onAdd, addedIds }: ExercisePickerProps) {
  const [search, setSearch] = useState("");
  const [selectedChip, setSelectedChip] = useState(0);
  const deferredSearch = useDeferredValue(search);

  // Pick first matching domain for the API query
  const activeDomains = DOMAIN_CHIPS[selectedChip]?.domains ?? [];
  const domainQuery = activeDomains[0] ?? "";

  const { data, isLoading } = useBuilderExercises(deferredSearch, domainQuery);

  // Client-side filter for multi-domain chips
  const exercises = (data?.exercises ?? []).filter((ex) => {
    if (activeDomains.length <= 1) return true;
    return ex.domain.some((d) => activeDomains.includes(d));
  });

  // A242: phase effort cue is identical across exercises — show it once.
  const effortBand = exercises[0]?.proposal?.effort_band ?? null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader className="pb-2">
          <div className="flex items-center justify-between">
            <DrawerTitle>Add Exercise</DrawerTitle>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onOpenChange(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DrawerHeader>

        <div className="px-4 pb-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search exercises..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Category chips */}
        <div className="flex gap-1.5 overflow-x-auto px-4 pb-3 no-scrollbar">
          {DOMAIN_CHIPS.map((chip, i) => (
            <button
              key={chip.label}
              type="button"
              className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                i === selectedChip
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              onClick={() => setSelectedChip(i)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {/* A242: phase effort-band cue (display-only, no RPE number) */}
        {effortBand && (
          <p className="px-4 pb-2 text-[11px] text-muted-foreground">
            <span className="font-medium text-foreground/80">This phase:</span> {effortBand}
          </p>
        )}

        {/* Exercise list */}
        <div className="flex-1 overflow-y-auto overscroll-contain px-4 pb-4 space-y-1" style={{ maxHeight: "55vh" }}>
            {isLoading && (
              <p className="text-sm text-muted-foreground text-center py-8">Loading...</p>
            )}
            {!isLoading && exercises.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">No exercises found</p>
            )}
            {exercises.map((ex) => {
              const isAdded = addedIds.has(ex.id);
              return (
                <div
                  key={ex.id}
                  className="flex items-start gap-3 rounded-lg border p-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-medium truncate">{ex.name}</p>
                      {isAdded && (
                        <Badge variant="outline" className="text-xs px-2 py-0.5 shrink-0 bg-green-500/20 text-green-400 border-green-500/30">
                          Added
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDefaults(ex)}
                    </p>
                    {lastTimeLabel(ex) && (
                      <p className="text-[11px] text-amber-500/90 mt-0.5">{lastTimeLabel(ex)}</p>
                    )}
                    {ex.equipment_required.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {ex.equipment_required.map((eq) => (
                          <Badge key={eq} variant="secondary" className="text-[10px] px-1.5 py-0">
                            {eq.replace(/_/g, " ")}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 shrink-0"
                    onClick={() => onAdd(exerciseToDefaults(ex), ex.name)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
      </DrawerContent>
    </Drawer>
  );
}
