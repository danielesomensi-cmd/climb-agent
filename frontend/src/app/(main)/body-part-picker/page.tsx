"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import {
  getBodyPartPickerOptions,
  getBodyPartEstimate,
  previewBodyPartSession,
  startBodyPartSession,
  type BodyPartOption,
  type BodyPartEquipmentOption,
  type BodyPartSession,
} from "@/lib/api";
import { invalidateWeekPlans } from "@/lib/invalidation";
import { useQueryClient } from "@tanstack/react-query";

type Step = "equipment" | "parts" | "preview";

const BODY_PART_ICONS: Record<string, string> = {
  fingers: "🖐️",
  forearms: "💪",
  biceps: "💪",
  triceps: "💪",
  shoulders: "🏋️",
  back_pulling: "🔝",
  chest: "🤜",
  core: "🔥",
  legs: "🦵",
  glutes: "🍑",
  hips: "🧘",
};

export default function BodyPartPickerPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const [step, setStep] = useState<Step>("equipment");
  const [equipmentMode, setEquipmentMode] = useState<string>("");
  const [gymId, setGymId] = useState<string | undefined>(undefined);
  const [selectedParts, setSelectedParts] = useState<Set<string>>(new Set());
  const [includeCooldown, setIncludeCooldown] = useState(true);

  const [bodyParts, setBodyParts] = useState<BodyPartOption[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<BodyPartEquipmentOption[]>([]);
  const [preview, setPreview] = useState<BodyPartSession | null>(null);
  const [estimatedDuration, setEstimatedDuration] = useState<number>(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Load options on mount
  useEffect(() => {
    setLoading(true);
    getBodyPartPickerOptions()
      .then((data) => {
        setBodyParts(data.body_parts);
        setEquipmentOptions(data.equipment_options);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load options"))
      .finally(() => setLoading(false));
  }, []);

  // Reload body parts when equipment changes (more accurate counts/enabled flags)
  useEffect(() => {
    if (!equipmentMode) return;
    setLoading(true);
    getBodyPartPickerOptions(equipmentMode, gymId)
      .then((data) => setBodyParts(data.body_parts))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load body parts"))
      .finally(() => setLoading(false));
  }, [equipmentMode, gymId]);

  // Live duration estimate
  useEffect(() => {
    if (selectedParts.size === 0) {
      setEstimatedDuration(0);
      return;
    }
    const parts = Array.from(selectedParts);
    getBodyPartEstimate(parts, includeCooldown)
      .then((r) => setEstimatedDuration(r.estimated_duration_min))
      .catch(() => {});
  }, [selectedParts, includeCooldown]);

  const handleEquipmentSelect = (opt: BodyPartEquipmentOption) => {
    setEquipmentMode(opt.mode);
    setGymId(opt.gym_id);
    setStep("parts");
  };

  const toggleBodyPart = (id: string, enabled: boolean) => {
    if (!enabled) return;
    setSelectedParts((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handlePreview = async () => {
    setError(null);
    setLoading(true);
    try {
      const session = await previewBodyPartSession({
        body_parts: Array.from(selectedParts),
        equipment_mode: equipmentMode,
        gym_id: gymId,
        include_cooldown: includeCooldown,
      });
      setPreview(session);
      setStep("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoading(false);
    }
  };

  const handleStart = useCallback(async () => {
    setError(null);
    setStarting(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const result = await startBodyPartSession({
        body_parts: Array.from(selectedParts),
        equipment_mode: equipmentMode,
        gym_id: gymId,
        include_cooldown: includeCooldown,
        target_date: today,
        slot: "evening",
        location: gymId ? "gym" : equipmentMode === "home" ? "home" : "home",
      });
      invalidateWeekPlans(qc);
      const sid = result.session?.session_id;
      if (sid) {
        router.push(`/guided/${today}/${sid}`);
      } else {
        router.push("/today");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
      setStarting(false);
    }
  }, [selectedParts, equipmentMode, gymId, includeCooldown, qc, router]);

  const canPreview = selectedParts.size > 0 && equipmentMode;

  const selectedPartsOrdered = useMemo(
    () => bodyParts.filter((bp) => selectedParts.has(bp.id)),
    [bodyParts, selectedParts]
  );

  return (
    <>
      <TopBar
        title="Body Part Training"
        backHref={step === "equipment" ? "/free-session" : undefined}
      />
      <main className="px-4 py-4 max-w-lg mx-auto">
        {error && (
          <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* STEP: Equipment selector */}
        {step === "equipment" && (
          <div className="flex flex-col gap-3">
            <h2 className="text-center text-lg font-semibold mb-2">Choose equipment</h2>
            <p className="text-center text-sm text-muted-foreground mb-2">
              We&apos;ll filter exercises to what you have available.
            </p>
            {loading && equipmentOptions.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
            ) : (
              equipmentOptions.map((opt) => (
                <button
                  key={`${opt.mode}-${opt.gym_id ?? ""}`}
                  onClick={() => handleEquipmentSelect(opt)}
                  className="flex items-center justify-between rounded-xl border bg-card p-4 text-left transition-all hover:border-primary/40 active:scale-[0.99]"
                >
                  <span className="font-medium">{opt.label}</span>
                  <span className="text-muted-foreground">›</span>
                </button>
              ))
            )}
          </div>
        )}

        {/* STEP: Body part grid */}
        {step === "parts" && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setStep("equipment")}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                ← Equipment
              </button>
              <div className="text-xs text-muted-foreground">
                {equipmentOptions.find((o) => o.mode === equipmentMode && o.gym_id === gymId)?.label}
              </div>
            </div>

            <div>
              <h2 className="text-center text-lg font-semibold">Which body parts?</h2>
              <p className="text-center text-sm text-muted-foreground">
                Tap to select. You can pick more than one.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              {bodyParts.map((bp) => {
                const isSelected = selectedParts.has(bp.id);
                const disabled = !bp.enabled;
                return (
                  <button
                    key={bp.id}
                    onClick={() => toggleBodyPart(bp.id, bp.enabled)}
                    disabled={disabled}
                    className={`flex flex-col items-start gap-1.5 rounded-xl border p-3 text-left transition-all ${
                      disabled
                        ? "border-border/50 bg-card/40 opacity-50 cursor-not-allowed"
                        : isSelected
                          ? "border-primary bg-primary/10"
                          : "border-border bg-card hover:border-primary/40 active:scale-[0.99]"
                    }`}
                  >
                    <div className="flex w-full items-start justify-between">
                      <div className="text-2xl">{BODY_PART_ICONS[bp.id] ?? "💪"}</div>
                      {isSelected && (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
                          ✓
                        </div>
                      )}
                    </div>
                    <div className="font-medium text-sm">{bp.label}</div>
                    <div className="text-[11px] text-muted-foreground leading-tight">
                      {disabled ? "Not available" : `${bp.exercise_count} exercises`}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Cooldown toggle */}
            <label className="flex items-center justify-between rounded-xl border bg-card p-3">
              <span className="text-sm">Include mobility cooldown</span>
              <input
                type="checkbox"
                checked={includeCooldown}
                onChange={(e) => setIncludeCooldown(e.target.checked)}
                className="h-5 w-5"
              />
            </label>

            {/* Footer — live counter + action */}
            <div className="sticky bottom-4 mt-2 rounded-xl border bg-background/95 backdrop-blur p-3 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm">
                  <span className="font-semibold">{selectedParts.size}</span>{" "}
                  <span className="text-muted-foreground">
                    selected · ~{estimatedDuration} min
                  </span>
                </div>
              </div>
              <Button
                onClick={handlePreview}
                disabled={!canPreview || loading}
                className="w-full"
              >
                {loading ? "Loading…" : "Preview session"}
              </Button>
            </div>
          </div>
        )}

        {/* STEP: Preview */}
        {step === "preview" && preview && (
          <div className="flex flex-col gap-4">
            <button
              onClick={() => setStep("parts")}
              className="text-sm text-muted-foreground hover:text-foreground text-left"
            >
              ← Edit selection
            </button>

            <div className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold text-lg">{preview.name}</h2>
              <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                <span>~{preview.estimated_duration_minutes} min</span>
                <span>·</span>
                <span>Load {preview.estimated_load_score}</span>
                <span>·</span>
                <span>{preview.exercises.length} exercises</span>
              </div>
            </div>

            {/* Group exercises by body part */}
            {selectedPartsOrdered.map((bp) => {
              const partExercises = preview.exercises.filter((e) => e.body_part === bp.id);
              if (partExercises.length === 0) return null;
              return (
                <div key={bp.id} className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                    <span>{BODY_PART_ICONS[bp.id] ?? "💪"}</span>
                    <span>{bp.label}</span>
                  </h3>
                  {partExercises.map((ex, idx) => (
                    <div
                      key={`${ex.exercise_id}-${idx}`}
                      className="rounded-lg border bg-card p-3"
                    >
                      <div className="font-medium text-sm">
                        {ex.exercise_id.replace(/_/g, " ")}
                      </div>
                      <ExercisePrescription prescription={ex.prescription} />
                    </div>
                  ))}
                </div>
              );
            })}

            {/* Cooldown exercises (body_part='cooldown') */}
            {preview.exercises.some((e) => e.body_part === "cooldown") && (
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Cooldown
                </h3>
                {preview.exercises
                  .filter((e) => e.body_part === "cooldown")
                  .map((ex, idx) => (
                    <div
                      key={`cooldown-${ex.exercise_id}-${idx}`}
                      className="rounded-lg border bg-card p-3"
                    >
                      <div className="font-medium text-sm">
                        {ex.exercise_id.replace(/_/g, " ")}
                      </div>
                      <ExercisePrescription prescription={ex.prescription} />
                    </div>
                  ))}
              </div>
            )}

            <div className="sticky bottom-4 mt-2 rounded-xl border bg-background/95 backdrop-blur p-3 shadow-lg">
              <Button
                onClick={handleStart}
                disabled={starting}
                className="w-full"
              >
                {starting ? "Starting…" : "Start now"}
              </Button>
            </div>
          </div>
        )}
      </main>
    </>
  );
}

function ExercisePrescription({ prescription }: { prescription: Record<string, unknown> }) {
  if (!prescription) return null;
  const bits: string[] = [];
  const sets = prescription.sets;
  const reps = prescription.reps;
  const workSec = prescription.work_seconds;
  const restSec = prescription.rest_between_sets_seconds;
  const load = prescription.suggested_external_load_kg;

  if (sets) {
    if (reps) bits.push(`${sets} × ${reps} reps`);
    else if (workSec) bits.push(`${sets} × ${workSec}s`);
    else bits.push(`${sets} sets`);
  }
  if (restSec) bits.push(`rest ${restSec}s`);
  if (typeof load === "number" && load > 0) bits.push(`+${load}kg`);

  if (bits.length === 0) return null;
  return (
    <div className="text-xs text-muted-foreground mt-1">{bits.join(" · ")}</div>
  );
}
