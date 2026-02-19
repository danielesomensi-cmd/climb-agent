"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
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

type SlotData = { available: boolean; preferred_location: string; gym_id?: string };

interface Gym {
  name: string;
  equipment: string[];
}

interface AvailabilityEditorProps {
  initialAvailability: Record<string, Record<string, SlotData>>;
  initialPlanningPrefs: { target_training_days_per_week: number; hard_day_cap_per_week: number };
  gyms: Gym[];
  onSave: (availability: Record<string, Record<string, SlotData>>, planningPrefs: { target_training_days_per_week: number; hard_day_cap_per_week: number }) => void;
  onCancel: () => void;
}

export function AvailabilityEditor({
  initialAvailability,
  initialPlanningPrefs,
  gyms,
  onSave,
  onCancel,
}: AvailabilityEditorProps) {
  const [availability, setAvailability] = useState<Record<string, Record<string, SlotData>>>(
    () => JSON.parse(JSON.stringify(initialAvailability))
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
      gym_id: location === "home" ? undefined : current.gym_id,
    });
  };

  const setGymId = (day: string, slot: string, gymId: string) => {
    const current = getSlot(day, slot);
    updateSlot(day, slot, { ...current, gym_id: gymId });
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
            <div
              key={day.key}
              className="grid grid-cols-[auto_1fr_1fr_1fr] gap-1 items-start"
            >
              <p className="w-10 text-sm font-medium py-2">{day.label}</p>
              {SLOTS.map((slot) => {
                const s = getSlot(day.key, slot.key);
                return (
                  <div key={slot.key} className="space-y-1">
                    <button
                      type="button"
                      className={`w-full rounded-md border px-2 py-2 text-xs transition-colors ${
                        s.available
                          ? "border-primary bg-primary/10 text-primary font-medium"
                          : "border-muted bg-muted/30 text-muted-foreground hover:border-primary/40"
                      }`}
                      onClick={() => toggleSlot(day.key, slot.key)}
                    >
                      {s.available ? "Yes" : "-"}
                    </button>

                    {s.available && (
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
                                <SelectItem key={i} value={g.name || `gym-${i}`}>
                                  {g.name || `Gym ${i + 1}`}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
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
              min={3}
              max={7}
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
              min={2}
              max={4}
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
          onClick={() => onSave(availability, planningPrefs)}
        >
          Save & regenerate plan
        </Button>
      </div>
    </div>
  );
}
