"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DEFAULT_ROTATION,
  MAX_ROTATION_LENGTH,
  ROLE_LABELS,
  SLOT_ROLES,
  effectiveRole,
  effectiveRotation,
  isComplementary,
  isPrimaryCapable,
  moveItem,
  parseMaxMinutes,
  withFocus,
  withMaxMinutes,
  withRole,
  type StructuredSlot,
} from "@/lib/slot-structure";
import { FOCUS_LABELS, FOCUS_ORDER, describeKeptPreview, type KeptSession } from "@/lib/week-alerts";
import type { FocusFamily, SlotRole } from "@/lib/types";

const WEEKDAYS = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

const SLOTS = [
  { key: "morning", label: "Morning" },
  { key: "lunch", label: "Lunch" },
  { key: "evening", label: "Evening" },
];

// A300 — role / max_minutes / focus ride along on the slot (optional).
type SlotData = StructuredSlot;

export type EditorPlanningPrefs = {
  target_training_days_per_week: number;
  hard_day_cap_per_week: number;
  target_sessions_per_week?: number;
  /** A300 — sent only when the user edited it (byte-identical plans otherwise). */
  complementary_rotation?: FocusFamily[];
};

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface AvailabilityEditorProps {
  initialAvailability: Record<string, Record<string, unknown>>;
  initialPlanningPrefs: Omit<EditorPlanningPrefs, "complementary_rotation"> & { complementary_rotation?: FocusFamily[] | null };
  gyms: Gym[];
  onSave: (availability: Record<string, Record<string, unknown>>, planningPrefs: EditorPlanningPrefs) => void;
  /**
   * B369 / A300 — the user's own sessions from today on in the current week:
   * the regeneration keeps them. `undefined` = not known yet (week not loaded).
   */
  keptPreview?: KeptSession[];
  onCancel: () => void;
}

export function AvailabilityEditor({
  initialAvailability,
  initialPlanningPrefs,
  gyms,
  onSave,
  onCancel,
  keptPreview,
}: AvailabilityEditorProps) {
  // Extract slots (non _day_meta keys) as SlotData.
  // Migrate legacy _day_meta other_activity into per-slot preferred_location="other_sport".
  const [availability, setAvailability] = useState<Record<string, Record<string, SlotData>>>(
    () => {
      const parsed = JSON.parse(JSON.stringify(initialAvailability));
      const result: Record<string, Record<string, SlotData>> = {};
      for (const [day, dayData] of Object.entries(parsed)) {
        if (!dayData || typeof dayData !== "object") continue; // B151: skip null/removed days
        result[day] = {};
        const dd = dayData as Record<string, unknown>;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const meta = dd._day_meta as any;
        for (const [key, val] of Object.entries(dd)) {
          if (key !== "_day_meta") result[day][key] = val as SlotData;
        }
        // Migrate legacy day-level other_activity to per-slot
        if (meta?.other_activity && meta?.other_activity_slot) {
          const slotKey = meta.other_activity_slot as string;
          result[day][slotKey] = {
            available: true,
            preferred_location: "other_sport",
            other_activity_name: meta.other_activity_name ?? "",
            reduce_intensity_after: meta.reduce_intensity_after ?? false,
          };
        }
      }
      return result;
    }
  );
  const [planningPrefs, setPlanningPrefs] = useState(() => {
    // The rotation lives in its own state (sent only when edited).
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { complementary_rotation: _rot, ...rest } = initialPlanningPrefs;
    return rest as EditorPlanningPrefs;
  });
  // A300 — the stored slots, to tell "clear a field I set" (write the neutral
  // value over it) from "leave a field I never set" (no key at all).
  const initialSlots = useMemo(
    () => JSON.parse(JSON.stringify(initialAvailability ?? {})) as Record<string, Record<string, Partial<SlotData>>>,
    [initialAvailability],
  );
  // A300 — complementary rotation: ordered families; `rotationDirty` gates the
  // patch so an untouched editor sends exactly what it sent before A300.
  const [rotation, setRotation] = useState<FocusFamily[]>(() =>
    effectiveRotation(initialPlanningPrefs.complementary_rotation),
  );
  const [rotationDirty, setRotationDirty] = useState(false);
  const editRotation = (next: FocusFamily[]) => {
    setRotation(next);
    setRotationDirty(true);
  };
  // Raw text of the max-minutes inputs, keyed "day.slot" (validated on the fly).
  const [minutesText, setMinutesText] = useState<Record<string, string>>({});

  const getSlot = (day: string, slot: string): SlotData => {
    return availability[day]?.[slot] ?? { available: false, preferred_location: "home" };
  };

  const updateSlot = (day: string, slot: string, value: SlotData) => {
    setAvailability((prev) => ({
      ...prev,
      [day]: { ...(prev[day] ?? {}), [slot]: value },
    }));
  };

  const toggleSlot = (day: string, slot: string) => {
    const current = getSlot(day, slot);
    updateSlot(day, slot, {
      // A300: keep role / max_minutes / focus across an off→on toggle.
      ...current,
      available: !current.available,
      preferred_location: current.preferred_location || "home",
      gym_id: current.gym_id,
    });
  };

  const initialSlot = (day: string, slot: string) => initialSlots[day]?.[slot];
  const setRole = (day: string, slot: string, role: SlotRole) =>
    updateSlot(day, slot, withRole(getSlot(day, slot), role, initialSlot(day, slot)));
  const setFocus = (day: string, slot: string, focus: FocusFamily | null) =>
    updateSlot(day, slot, withFocus(getSlot(day, slot), focus, initialSlot(day, slot)));
  const setMinutes = (day: string, slot: string, raw: string) => {
    setMinutesText((m) => ({ ...m, [`${day}.${slot}`]: raw }));
    const parsed = parseMaxMinutes(raw);
    if (parsed === null || !Number.isNaN(parsed)) {
      updateSlot(day, slot, withMaxMinutes(getSlot(day, slot), parsed, initialSlot(day, slot)));
    }
  };
  const minutesValue = (day: string, slot: string): string => {
    const typed = minutesText[`${day}.${slot}`];
    if (typed !== undefined) return typed;
    const mm = getSlot(day, slot).max_minutes;
    return typeof mm === "number" ? String(mm) : "";
  };
  const activeSlots = WEEKDAYS.flatMap((day) =>
    SLOTS.filter((slot) => {
      const s = getSlot(day.key, slot.key);
      return s.available && s.preferred_location !== "other_sport";
    }).map((slot) => ({ day, slot })),
  );
  const invalidMinutes = activeSlots.some(({ day, slot }) => {
    const typed = minutesText[`${day.key}.${slot.key}`];
    return typed !== undefined && Number.isNaN(parseMaxMinutes(typed));
  });
  const complementaryCount = activeSlots.filter(({ day, slot }) => isComplementary(getSlot(day.key, slot.key))).length;
  const showRotation = complementaryCount > 0 || rotationDirty || initialPlanningPrefs.complementary_rotation != null;

  const setLocation = (day: string, slot: string, location: string) => {
    const current = getSlot(day, slot);
    updateSlot(day, slot, {
      ...current,
      preferred_location: location,
      gym_id: location === "home" || location === "other_sport" ? undefined : current.gym_id,
      other_activity_name: location === "other_sport" ? (current.other_activity_name ?? "") : undefined,
      reduce_intensity_after: location === "other_sport" ? (current.reduce_intensity_after ?? false) : undefined,
    });
  };

  const setGymId = (day: string, slot: string, gymId: string) => {
    const current = getSlot(day, slot);
    updateSlot(day, slot, { ...current, gym_id: gymId });
  };

  // Count unique days with at least one training slot (excludes other_sport).
  // A300: and excludes complementary slots — they have their own budget
  // (one session each), outside the training-days / sessions targets.
  const availableDays = WEEKDAYS.filter((day) =>
    SLOTS.some((slot) => isPrimaryCapable(getSlot(day.key, slot.key)))
  ).length;

  // A283 — gli SLOT spuntati, che non sono i giorni: chi si allena spezzato
  // (complementari a pranzo, arrampicata la sera) ne ha più dei giorni, ed è il
  // tetto naturale di quante sessioni si possono davvero piazzare.
  const availableSlots = WEEKDAYS.reduce(
    (total, day) =>
      total +
      SLOTS.filter((slot) => isPrimaryCapable(getSlot(day.key, slot.key))).length,
    0,
  );

  const trainingDaysMax = Math.max(1, availableDays);
  const hardDaysMax = Math.max(1, planningPrefs.target_training_days_per_week);
  const sessionsMax = Math.max(trainingDaysMax, availableSlots);
  // Default retrocompatibile: chi non tocca il controllo resta a "una al giorno".
  const targetSessions =
    planningPrefs.target_sessions_per_week ?? planningPrefs.target_training_days_per_week;
  const splitAvailable = availableSlots > availableDays;

  // Auto-clamp sliders when caps shrink.
  // B355 — il clamp DEVE finire nello state: `handleSave` invia `planningPrefs`
  // al backend, quindi un valore solo derivato per il render lascerebbe salvare
  // il numero fuori scala. Il setState in effect è il prezzo di questo
  // invariante, non una svista.
  useEffect(() => {
    if (availableDays > 0 && planningPrefs.target_training_days_per_week > availableDays) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlanningPrefs((p) => ({ ...p, target_training_days_per_week: availableDays }));
    }
  }, [availableDays, planningPrefs.target_training_days_per_week]);

  useEffect(() => {
    const max = planningPrefs.target_training_days_per_week;
    if (max > 0 && planningPrefs.hard_day_cap_per_week > max) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlanningPrefs((p) => ({ ...p, hard_day_cap_per_week: max }));
    }
  }, [planningPrefs.target_training_days_per_week, planningPrefs.hard_day_cap_per_week]);

  // A283 — stesso invariante degli altri due clamp: il valore salvato non deve
  // mai uscire dalla scala. Se togli slot, o alzi i giorni sopra le sessioni, il
  // numero si riallinea invece di partire fuori scala verso il motore.
  useEffect(() => {
    const current = planningPrefs.target_sessions_per_week;
    if (current == null) return;
    const clamped = Math.min(Math.max(current, planningPrefs.target_training_days_per_week), sessionsMax);
    if (clamped !== current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlanningPrefs((p) => ({ ...p, target_sessions_per_week: clamped }));
    }
  }, [
    planningPrefs.target_sessions_per_week,
    planningPrefs.target_training_days_per_week,
    sessionsMax,
  ]);

  const handleSave = () => {
    // D150: Only include days that have at least one configured slot.
    // Empty day dicts {} would be misinterpreted by the planner as
    // "fully available" — omitting them ensures they become rest days.
    const enriched: Record<string, Record<string, unknown>> = {};
    for (const day of WEEKDAYS) {
      const dayData = availability[day.key] ?? {};
      const hasActiveSlot = SLOTS.some((s) => {
        const slot = dayData[s.key];
        return slot && (slot.available || slot.preferred_location === "other_sport");
      });
      if (hasActiveSlot) {
        // B272: explicitly null legacy _day_meta — the load-time migration
        // converts it to per-slot other_sport, but deep-merge would keep the
        // stale key server-side and the planner reads BOTH sources
        // (double-count risk for pre-migration users).
        enriched[day.key] = { ...dayData, _day_meta: null };
      }
    }
    onSave(enriched, rotationDirty ? { ...planningPrefs, complementary_rotation: rotation } : planningPrefs);
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Availability grid</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Grid header */}
          <div className="grid grid-cols-[auto_1fr_1fr_1fr] gap-1 text-center">
            <div />
            {SLOTS.map((s) => (
              <p key={s.key} className="text-xs font-medium text-muted-foreground">
                {s.label}
              </p>
            ))}
          </div>

          {/* Grid rows */}
          {WEEKDAYS.map((day) => (
            <div key={day.key} className="space-y-1">
              <div className="grid grid-cols-[auto_1fr_1fr_1fr] gap-1 items-start">
                <p className="w-10 text-sm font-medium py-2">{day.label}</p>
                {SLOTS.map((slot) => {
                  const s = getSlot(day.key, slot.key);
                  return (
                    <div key={slot.key} className="space-y-1">
                      <button
                        type="button"
                        className={`w-full rounded-md border px-2 py-2 text-xs transition-colors ${
                          s.available || s.preferred_location === "other_sport"
                            ? "border-primary bg-primary/10 text-primary font-medium"
                            : "border-muted bg-muted/30 text-muted-foreground hover:border-primary/40"
                        }`}
                        onClick={() => {
                          if (s.preferred_location === "other_sport") {
                            // Toggle off: reset to unavailable
                            updateSlot(day.key, slot.key, { available: false, preferred_location: "home" });
                          } else {
                            toggleSlot(day.key, slot.key);
                          }
                        }}
                      >
                        {s.preferred_location === "other_sport" ? "Other" : s.available ? "Yes" : "-"}
                      </button>

                      {(s.available || s.preferred_location === "other_sport") && (
                        <div className="space-y-1">
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className={`flex-1 rounded text-[10px] px-1 py-0.5 border ${
                                s.preferred_location === "home"
                                  ? "border-primary bg-primary/10 text-primary"
                                  : "border-muted text-muted-foreground"
                              }`}
                              onClick={() => setLocation(day.key, slot.key, "home")}
                            >
                              Home
                            </button>
                            <button
                              type="button"
                              className={`flex-1 rounded text-[10px] px-1 py-0.5 border ${
                                s.preferred_location === "gym"
                                  ? "border-primary bg-primary/10 text-primary"
                                  : "border-muted text-muted-foreground"
                              }`}
                              onClick={() => setLocation(day.key, slot.key, "gym")}
                            >
                              Gym
                            </button>
                            <button
                              type="button"
                              className={`flex-1 rounded text-[10px] px-1 py-0.5 border ${
                                s.preferred_location === "other_sport"
                                  ? "border-warning/40 bg-warning/15 text-warning"
                                  : "border-muted text-muted-foreground"
                              }`}
                              onClick={() => setLocation(day.key, slot.key, "other_sport")}
                            >
                              Other
                            </button>
                          </div>

                          {s.preferred_location === "gym" && gyms.length > 0 && (
                            <Select
                              value={s.gym_id ?? ""}
                              onValueChange={(v) => setGymId(day.key, slot.key, v)}
                            >
                              <SelectTrigger className="h-6 text-[10px] w-full">
                                <SelectValue placeholder="Which?" />
                              </SelectTrigger>
                              <SelectContent>
                                {gyms.map((g, i) => (
                                  <SelectItem key={g.gym_id || i} value={g.gym_id || ""}>
                                    {g.name || `Gym ${i + 1}`}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}

                          {s.preferred_location === "other_sport" && (
                            <div className="space-y-1">
                              <Input
                                placeholder="e.g. Circus, Running"
                                className="h-6 text-[10px]"
                                value={s.other_activity_name ?? ""}
                                onChange={(e) =>
                                  updateSlot(day.key, slot.key, { ...s, other_activity_name: e.target.value })
                                }
                              />
                              <div className="flex items-center gap-1">
                                <Switch
                                  id={`reduce-${day.key}-${slot.key}`}
                                  className="scale-75"
                                  checked={s.reduce_intensity_after ?? false}
                                  onCheckedChange={(v) =>
                                    updateSlot(day.key, slot.key, { ...s, reduce_intensity_after: v })
                                  }
                                />
                                <Label htmlFor={`reduce-${day.key}-${slot.key}`} className="text-[10px]">
                                  Reduce next day
                                </Label>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          <p className="text-sm font-medium text-center text-muted-foreground">
            {availableDays} {availableDays === 1 ? "day" : "days"} with availability
            {complementaryCount > 0 &&
              ` · ${complementaryCount} complementary ${complementaryCount === 1 ? "slot" : "slots"}`}
          </p>
        </CardContent>
      </Card>

      {/* A300 — slot structure: role, time limit, complementary rotation */}
      {activeSlots.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Slot structure</CardTitle>
            <CardDescription>
              Primary slots get the climbing sessions of your phase. Complementary
              slots (e.g. a lunch break at a weights gym) get a short session from
              your rotation. &ldquo;Any&rdquo; works as before.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeSlots.map(({ day, slot }) => {
              const s = getSlot(day.key, slot.key);
              const role = effectiveRole(s);
              const id = `${day.key}-${slot.key}`;
              const typed = minutesText[`${day.key}.${slot.key}`];
              const bad = typed !== undefined && Number.isNaN(parseMaxMinutes(typed));
              return (
                <div key={id} className="space-y-1.5 rounded-md border p-2" data-testid={`slot-structure-${id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">
                      {day.label} · {slot.label}
                    </p>
                    <div className="flex gap-1" role="radiogroup" aria-label={`${day.label} ${slot.label} role`}>
                      {SLOT_ROLES.map((r) => (
                        <button
                          key={r}
                          type="button"
                          role="radio"
                          aria-checked={role === r}
                          className={`rounded px-2 py-1 text-[11px] border ${
                            role === r
                              ? "border-primary bg-primary/10 text-primary font-medium"
                              : "border-muted text-muted-foreground"
                          }`}
                          onClick={() => setRole(day.key, slot.key, r)}
                        >
                          {ROLE_LABELS[r]}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Label htmlFor={`mm-${id}`} className="text-xs text-muted-foreground">
                      Max minutes
                    </Label>
                    <Input
                      id={`mm-${id}`}
                      inputMode="numeric"
                      placeholder="no limit"
                      className={`h-7 w-20 text-xs ${bad ? "border-danger" : ""}`}
                      value={minutesValue(day.key, slot.key)}
                      onChange={(e) => setMinutes(day.key, slot.key, e.target.value)}
                      aria-invalid={bad}
                    />
                    {role === "complementary" && (
                      <Select
                        value={s.focus ?? "auto"}
                        onValueChange={(v) => setFocus(day.key, slot.key, v === "auto" ? null : (v as FocusFamily))}
                      >
                        <SelectTrigger className="h-7 text-xs w-auto min-w-[9rem]" aria-label="Focus">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="auto">Auto (rotation)</SelectItem>
                          {FOCUS_ORDER.map((f) => (
                            <SelectItem key={f} value={f}>
                              {FOCUS_LABELS[f]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                  {bad && (
                    <p className="text-[11px] text-danger">Use a whole number between 10 and 240, or leave it empty.</p>
                  )}
                </div>
              );
            })}

            {showRotation && (
              <div className="space-y-2 pt-2" data-testid="complementary-rotation">
                <div>
                  <p className="text-sm font-medium">Complementary rotation</p>
                  <p className="text-xs text-muted-foreground">
                    The planner pairs these with your complementary slots by itself, each
                    week, from what your evenings hold — HIIT never on or before a max day
                    (at most one a week, it never counts as a hard day; zone 2 in deload),
                    biceps not in the 24 h before heavy pulling, legs not in the 48 h
                    before a limit or outdoor day. Cardio runs on the treadmill.
                  </p>
                </div>
                {rotation.length === 0 ? (
                  <p className="text-xs text-warning">
                    Empty rotation: complementary slots stay free.
                  </p>
                ) : (
                  <ol className="space-y-1">
                    {rotation.map((f, i) => (
                      <li key={`${f}-${i}`} className="flex items-center gap-2 text-sm">
                        <span className="w-5 text-xs text-muted-foreground tabular-nums">{i + 1}.</span>
                        <span className="flex-1">{FOCUS_LABELS[f]}</span>
                        <button
                          type="button"
                          className="p-1 text-muted-foreground disabled:opacity-30"
                          aria-label={`Move ${FOCUS_LABELS[f]} up`}
                          disabled={i === 0}
                          onClick={() => editRotation(moveItem(rotation, i, -1))}
                        >
                          <ArrowUp className="size-3.5" />
                        </button>
                        <button
                          type="button"
                          className="p-1 text-muted-foreground disabled:opacity-30"
                          aria-label={`Move ${FOCUS_LABELS[f]} down`}
                          disabled={i === rotation.length - 1}
                          onClick={() => editRotation(moveItem(rotation, i, 1))}
                        >
                          <ArrowDown className="size-3.5" />
                        </button>
                        <button
                          type="button"
                          className="p-1 text-muted-foreground"
                          aria-label={`Remove ${FOCUS_LABELS[f]}`}
                          onClick={() => editRotation(rotation.filter((_, j) => j !== i))}
                        >
                          <X className="size-3.5" />
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
                <div className="flex flex-wrap gap-1">
                  {FOCUS_ORDER.map((f) => (
                    <button
                      key={f}
                      type="button"
                      className="rounded border border-muted px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/40 disabled:opacity-40"
                      disabled={rotation.length >= MAX_ROTATION_LENGTH}
                      onClick={() => editRotation([...rotation, f])}
                    >
                      + {FOCUS_LABELS[f]}
                    </button>
                  ))}
                  {rotationDirty && (
                    <button
                      type="button"
                      className="rounded px-2 py-1 text-[11px] text-muted-foreground underline"
                      onClick={() => editRotation([...DEFAULT_ROTATION])}
                    >
                      Reset to all four
                    </button>
                  )}
                </div>
                {complementaryCount > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {complementaryCount} complementary {complementaryCount === 1 ? "slot" : "slots"} a week
                    {rotation.length > 0 && complementaryCount > rotation.length
                      ? ` — up to ${complementaryCount - rotation.length} may stay free (the rotation is shorter).`
                      : "."}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Planning preferences */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Training preferences</CardTitle>
          <CardDescription>
            Hard sessions include max hang, limit bouldering, power training
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Training days per week</Label>
              <span className="text-sm font-medium tabular-nums">
                {planningPrefs.target_training_days_per_week}
              </span>
            </div>
            <Slider
              min={1}
              max={trainingDaysMax}
              step={1}
              value={[planningPrefs.target_training_days_per_week]}
              onValueChange={([v]) =>
                setPlanningPrefs((p) => ({ ...p, target_training_days_per_week: v }))
              }
            />
          </div>

          {/* A283 — compare solo se hai davvero più fasce che giorni: a chi si
              allena una volta al giorno questo controllo non dice nulla. */}
          {splitAvailable && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Sessions per week</Label>
                <span className="text-sm font-medium tabular-nums">{targetSessions}</span>
              </div>
              <Slider
                min={trainingDaysMax}
                max={sessionsMax}
                step={1}
                value={[Math.min(Math.max(targetSessions, trainingDaysMax), sessionsMax)]}
                onValueChange={([v]) =>
                  setPlanningPrefs((p) => ({ ...p, target_sessions_per_week: v }))
                }
              />
              <p className="text-xs text-muted-foreground">
                You have {availableSlots} slots across {availableDays}{" "}
                {availableDays === 1 ? "day" : "days"}. Raise this above{" "}
                {planningPrefs.target_training_days_per_week} to train twice in a day —
                for example a complementary session at lunch and climbing in the
                evening. The extra sessions are never hard ones.
              </p>
            </div>
          )}

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Max hard sessions per week</Label>
              <span className="text-sm font-medium tabular-nums">
                {planningPrefs.hard_day_cap_per_week}
              </span>
            </div>
            <Slider
              min={1}
              max={hardDaysMax}
              step={1}
              value={[planningPrefs.hard_day_cap_per_week]}
              onValueChange={([v]) =>
                setPlanningPrefs((p) => ({ ...p, hard_day_cap_per_week: v }))
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* B369 / A300 — what the regeneration keeps, said before saving */}
      {keptPreview !== undefined && (
        <p className="text-xs text-muted-foreground" data-testid="kept-preview">
          Saving regenerates the weeks ahead with this structure.{" "}
          {describeKeptPreview(keptPreview)}{" "}
          Done and past sessions never change.
        </p>
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={invalidMinutes}
        >
          Save & regenerate plan
        </Button>
      </div>
    </div>
  );
}
