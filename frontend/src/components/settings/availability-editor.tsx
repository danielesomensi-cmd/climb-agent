"use client";

import { useEffect, useState } from "react";
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

type SlotData = { available: boolean; preferred_location: string; gym_id?: string; other_activity_name?: string; reduce_intensity_after?: boolean };

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface AvailabilityEditorProps {
  initialAvailability: Record<string, Record<string, unknown>>;
  initialPlanningPrefs: { target_training_days_per_week: number; hard_day_cap_per_week: number };
  gyms: Gym[];
  onSave: (availability: Record<string, Record<string, unknown>>, planningPrefs: { target_training_days_per_week: number; hard_day_cap_per_week: number }) => void;
  onCancel: () => void;
}

export function AvailabilityEditor({
  initialAvailability,
  initialPlanningPrefs,
  gyms,
  onSave,
  onCancel,
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
  const [planningPrefs, setPlanningPrefs] = useState(
    () => ({ ...initialPlanningPrefs })
  );

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
      available: !current.available,
      preferred_location: current.preferred_location || "home",
      gym_id: current.gym_id,
    });
  };

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

  // Count unique days with at least one training slot (excludes other_sport)
  const availableDays = WEEKDAYS.filter((day) =>
    SLOTS.some((slot) => {
      const s = getSlot(day.key, slot.key);
      return s.available && s.preferred_location !== "other_sport";
    })
  ).length;

  const trainingDaysMax = Math.max(1, availableDays);
  const hardDaysMax = Math.max(1, planningPrefs.target_training_days_per_week);

  // Auto-clamp sliders when caps shrink
  useEffect(() => {
    if (availableDays > 0 && planningPrefs.target_training_days_per_week > availableDays) {
      setPlanningPrefs((p) => ({ ...p, target_training_days_per_week: availableDays }));
    }
  }, [availableDays]);

  useEffect(() => {
    const max = planningPrefs.target_training_days_per_week;
    if (max > 0 && planningPrefs.hard_day_cap_per_week > max) {
      setPlanningPrefs((p) => ({ ...p, hard_day_cap_per_week: max }));
    }
  }, [planningPrefs.target_training_days_per_week]);

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
    onSave(enriched, planningPrefs);
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
                                  ? "border-amber-500 bg-amber-500/10 text-amber-500"
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
          </p>
        </CardContent>
      </Card>

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

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
        >
          Save & regenerate plan
        </Button>
      </div>
    </div>
  );
}
