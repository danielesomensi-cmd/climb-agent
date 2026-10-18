"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { Search } from "lucide-react";
import { useSubmitLock } from "@/lib/hooks/use-submit-lock";
import { useCatalogExercises } from "@/lib/hooks/queries/use-catalog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { addExerciseToSession } from "@/lib/api";
import type { Exercise, WeekPlan } from "@/lib/types";
import { isExerciseCompatible } from "@/lib/equipment-filter";
import { loadInputLabel } from "@/lib/load-units";

/**
 * "Add exercise" for a planned session (moved out of session-card.tsx).
 *
 * B396 — two things changed with the move:
 * - it is loaded with `next/dynamic` from SessionCard and mounted on the first
 *   open, so it is one shared chunk fetched on demand instead of code inlined
 *   in session-card and shipped with every /today and /week first load;
 * - the catalog comes from the shared React Query cache (useCatalogExercises,
 *   immutable at runtime) instead of a component-local `getExercises()`: it
 *   used to be downloaded again (~100 KB gz) on the first open after every
 *   remount of the card.
 */
export function AddExerciseDialog({
  open,
  onOpenChange,
  date,
  sessionIndex,
  weekPlan,
  availableEquipment,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  date: string;
  sessionIndex: number;
  weekPlan: WeekPlan;
  availableEquipment: Set<string> | null;
  onSuccess: (updatedPlan?: WeekPlan) => void;
}) {
  const catalogQuery = useCatalogExercises(open);
  const catalog = useMemo<Exercise[]>(() => catalogQuery.data?.exercises ?? [], [catalogQuery.data]);
  const loading = catalogQuery.isLoading;
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Exercise | null>(null);
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(10);
  const [workSeconds, setWorkSeconds] = useState<number | null>(null);
  const [loadKg, setLoadKg] = useState<number | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [isTestMeasurement, setIsTestMeasurement] = useState(false);
  const [isDurationBased, setIsDurationBased] = useState(false);

  // Reset showAll when dialog closes
  // B355 — set-state-in-effect: sincronizzazione stato↔prop `open`. Il dialog
  // resta montato quando si chiude, quindi il "mostra tutti" va riportato al
  // default alla chiusura, non al render. Pattern corretto, non un bug.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!open) setShowAll(false);
  }, [open]);

  const filtered = useMemo(() => {
    let result = catalog;

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.exercise_id.toLowerCase().includes(q) ||
          (Array.isArray(e.domain) ? e.domain.some(d => d.toLowerCase().includes(q)) : String(e.domain ?? "").toLowerCase().includes(q)) ||
          (e.category?.toLowerCase().includes(q)) ||
          (e.description?.toLowerCase().includes(q))
      );
    }

    // Equipment filter (skip if no equipment context or showAll)
    if (availableEquipment && !showAll) {
      result = result.filter((e) => isExerciseCompatible(e, availableEquipment));
    }

    return result;
  }, [catalog, search, availableEquipment, showAll]);

  // Count hidden exercises for the toggle label
  const hiddenCount = useMemo(() => {
    if (!availableEquipment || showAll) return 0;
    // Count how many in the text-filtered set are hidden by equipment
    let textFiltered = catalog;
    if (search.trim()) {
      const q = search.toLowerCase();
      textFiltered = textFiltered.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.exercise_id.toLowerCase().includes(q) ||
          (Array.isArray(e.domain) ? e.domain.some(d => d.toLowerCase().includes(q)) : String(e.domain ?? "").toLowerCase().includes(q)) ||
          (e.category?.toLowerCase().includes(q)) ||
          (e.description?.toLowerCase().includes(q))
      );
    }
    return textFiltered.length - filtered.length;
  }, [catalog, search, availableEquipment, showAll, filtered.length]);

  const selectExercise = useCallback((ex: Exercise) => {
    setSelected(ex);
    const defaults = ex.prescription_defaults ?? {};
    const testMeas = ex.category === "test_measurement";
    const ws = (defaults.work_seconds as number | null) ?? null;
    const durationBased = !testMeas && ws != null && ws > 0;
    setIsTestMeasurement(testMeas);
    setIsDurationBased(durationBased);
    setSets((defaults.sets as number) ?? (testMeas ? 1 : 3));
    setReps((defaults.reps as number) ?? (testMeas ? 0 : 10));
    setWorkSeconds(ws);
    setLoadKg((defaults.load_kg as number | undefined) ?? 0);
    setError(null);
  }, []);

  // B330: ref-based lock — two taps in one React batch would otherwise add
  // the same exercise to the session twice.
  const { run: handleSubmit, busy: submitting } = useSubmitLock(async () => {
    if (!selected) return;
    setError(null);
    try {
      const overrides: Record<string, unknown> = { sets };
      if (isTestMeasurement) {
        // test_measurement: no reps, no load, no work_seconds — user reports result in guided mode
        overrides.reps = null;
        overrides.work_seconds = null;
      } else if (isDurationBased) {
        overrides.work_seconds = workSeconds;
        if (reps) overrides.reps = reps;
      } else {
        overrides.reps = reps;
      }
      if (loadKg != null && !isTestMeasurement) overrides.load_kg = loadKg;
      const payload = {
        date,
        session_index: sessionIndex,
        exercise_id: selected.exercise_id,
        prescription_override: overrides,
        week_plan: weekPlan,
      };
      const result = await addExerciseToSession(payload);
      onOpenChange(false);
      setSelected(null);
      setSearch("");
      onSuccess(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add exercise");
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Add Exercise</DialogTitle>
          <DialogDescription>Search the catalog and add an exercise to this session.</DialogDescription>
        </DialogHeader>

        {!selected ? (
          <div className="flex flex-col gap-3 flex-1 min-h-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                placeholder="Search exercises..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
                autoFocus
              />
            </div>
            {availableEquipment && (
              <div className="flex items-center justify-between">
                <button
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => setShowAll((v) => !v)}
                >
                  {showAll
                    ? "Show compatible only"
                    : `Show all exercises${hiddenCount > 0 ? ` (+${hiddenCount} hidden)` : ""}`}
                </button>
              </div>
            )}
            <div className="flex-1 overflow-y-auto space-y-1 min-h-0 max-h-[50vh]">
              {loading && <p className="text-xs text-muted-foreground p-2">Loading catalog...</p>}
              {catalogQuery.isError && catalog.length === 0 && (
                <p className="text-xs text-destructive p-2">
                  Couldn&apos;t load the exercise catalog. Check your connection and try again.
                </p>
              )}
              {!loading && !catalogQuery.isError && filtered.length === 0 && (
                <p className="text-xs text-muted-foreground p-2">No exercises found</p>
              )}
              {filtered.map((ex) => {
                const incompatible = showAll && availableEquipment && !isExerciseCompatible(ex, availableEquipment);
                return (
                  <button
                    key={ex.exercise_id}
                    className={`w-full text-left px-3 py-2 rounded-md hover:bg-accent transition-colors ${incompatible ? "opacity-50" : ""}`}
                    onClick={() => selectExercise(ex)}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium">{ex.name}</span>
                      {incompatible && (
                        <Badge variant="outline" className="text-[10px] text-warning border-warning/30">
                          Missing equipment
                        </Badge>
                      )}
                    </div>
                    {ex.description && (
                      <div className="text-xs text-muted-foreground/80 truncate">{ex.description}</div>
                    )}
                    <div className="text-xs text-muted-foreground">
                      {Array.isArray(ex.domain) ? ex.domain.join(", ") : ex.domain}
                      {ex.category && ` · ${ex.category}`}
                      {ex.equipment_required?.length > 0 && ` · ${ex.equipment_required.join(", ")}`}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-md border p-3">
              <div className="text-sm font-medium">{selected.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{Array.isArray(selected.domain) ? selected.domain.join(", ") : selected.domain}</div>
            </div>

            {isTestMeasurement ? (
              <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-sm font-medium">1 × max attempt</p>
                <p className="text-xs text-muted-foreground mt-1">
                  You&apos;ll record the result during the guided session.
                </p>
              </div>
            ) : (
              <div className={`grid ${isDurationBased ? "grid-cols-3" : "grid-cols-3"} gap-3`}>
                <div>
                  <Label className="text-xs">Sets</Label>
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={20}
                    value={sets}
                    onChange={(e) => setSets(Number(e.target.value))}
                  />
                </div>
                {isDurationBased ? (
                  <div>
                    <Label className="text-xs">Duration (s)</Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={600}
                      value={workSeconds ?? 0}
                      onChange={(e) => setWorkSeconds(Number(e.target.value))}
                    />
                  </div>
                ) : (
                  <div>
                    <Label className="text-xs">Reps</Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={100}
                      value={reps}
                      onChange={(e) => setReps(Number(e.target.value))}
                    />
                  </div>
                )}
                <div>
                  <Label className="text-xs">{loadInputLabel(selected.load_unit, "Additional weight (kg)")}</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={0.5}
                    value={loadKg ?? 0}
                    onChange={(e) => setLoadKg(e.target.value ? Number(e.target.value) : 0)}
                  />
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {selected.load_unit === "per_dumbbell"
                      ? "The weight of one dumbbell — not the sum of the two."
                      : selected.load_unit === "implement"
                        ? "The weight of the dumbbell or kettlebell."
                        : "Added to bodyweight. Enter 0 for BW only."}
                  </p>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}

            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setSelected(null)}>
                Back
              </Button>
              <Button className="flex-1" onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Adding..." : "Add exercise"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
