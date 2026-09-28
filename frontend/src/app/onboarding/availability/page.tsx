"use client";

import { useEffect } from "react";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { defaultTrainingLocation } from "@/lib/training-location";
import { StepNav } from "@/components/onboarding/step-nav";
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

export default function AvailabilityPage() {
  const { data, update } = useOnboarding();
  const availability = data.availability;
  const planningPrefs = data.planning_prefs;
  const gyms = data.equipment.gyms;

  // B322: default to the place the user can actually train (see lib/training-location).
  const defaultLocation = defaultTrainingLocation(data.equipment);

  // No separate dayMeta state needed — other_sport is stored per-slot

  const getSlot = (day: string, slot: string): SlotData => {
    return availability[day]?.[slot] ?? { available: false, preferred_location: defaultLocation };
  };

  const setSlot = (day: string, slot: string, value: SlotData) => {
    const dayData = { ...(availability[day] ?? {}), [slot]: value };
    update("availability", { ...availability, [day]: dayData });
  };

  const toggleSlot = (day: string, slot: string) => {
    const current = getSlot(day, slot);
    setSlot(day, slot, {
      available: !current.available,
      preferred_location: current.preferred_location || defaultLocation,
      gym_id: current.gym_id,
    });
  };

  const setLocation = (day: string, slot: string, location: string) => {
    const current = getSlot(day, slot);
    setSlot(day, slot, {
      ...current,
      preferred_location: location,
      gym_id: location === "home" || location === "other_sport" ? undefined : current.gym_id,
      other_activity_name: location === "other_sport" ? (current.other_activity_name ?? "") : undefined,
      reduce_intensity_after: location === "other_sport" ? (current.reduce_intensity_after ?? false) : undefined,
    });
  };

  const updateSlot = (day: string, slot: string, value: SlotData) => {
    setSlot(day, slot, value);
  };

  const setGymId = (day: string, slot: string, gymId: string) => {
    const current = getSlot(day, slot);
    setSlot(day, slot, { ...current, gym_id: gymId });
  };

  const setPlanningPref = (
    field: keyof typeof planningPrefs,
    value: number,
  ) => {
    update("planning_prefs", { ...planningPrefs, [field]: value });
  };

  // Count unique days with at least one training slot (excludes other_sport)
  const availableDays = WEEKDAYS.filter((day) =>
    SLOTS.some((slot) => {
      const s = getSlot(day.key, slot.key);
      return s.available && s.preferred_location !== "other_sport";
    })
  ).length;

  /**
   * A245 Phase D (F30) — the gate accepted a slot marked `other_sport`, but
   * `availableDays` above deliberately EXCLUDES those. So marking only "Other
   * sport" unlocked Next with zero climbing days, `target_training_days_per_week`
   * stayed at its default of 4, and the user got a plan with no climbing in it —
   * discovered only afterwards. The gate now agrees with the counter.
   *
   * F18: expressed as blockers rather than a disabled button.
   */
  const availabilityBlockers = availableDays === 0
    ? ["Mark at least one slot you can train in (an 'Other sport' slot doesn't count as a training day)"]
    : [];

  const trainingDaysMax = Math.max(1, availableDays);
  const hardDaysMax = Math.max(1, planningPrefs.target_training_days_per_week);

  // Auto-clamp sliders when caps shrink
  // B355 — dipendenza volutamente sul solo cap: l'effect deve reagire a
  // "l'utente ha tolto disponibilità", non a ogni tocco dello slider. Aggiungere
  // il valore corrente (e `setPlanningPref`, ricreata a ogni render perché chiude
  // su `planningPrefs`) farebbe girare l'effect in continuo su ogni update del
  // draft di onboarding.
  useEffect(() => {
    if (availableDays > 0 && planningPrefs.target_training_days_per_week > availableDays) {
      setPlanningPref("target_training_days_per_week", availableDays);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableDays]);

  // B355 — stesso ragionamento: il clamp scatta quando si abbassa il tetto dei
  // giorni di allenamento, non quando si muove lo slider dei giorni hard.
  useEffect(() => {
    const max = planningPrefs.target_training_days_per_week;
    if (max > 0 && planningPrefs.hard_day_cap_per_week > max) {
      setPlanningPref("hard_day_cap_per_week", max);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planningPrefs.target_training_days_per_week]);

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">When you train</CardTitle>
          <CardDescription>
            Outdoor days can be added later in your weekly plan based on weather and season.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {gyms.length === 0 && (
            <div className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
              <strong>Want to train at a gym?</strong> Go back to the Locations step and add at least one gym. Even a generic gym with all equipment selected will work — you can refine it later.
            </div>
          )}
          <div className="rounded-md border border-info/30 bg-info/10 px-4 py-3 text-sm text-info">
            Set your typical training week. The planner builds sessions around your schedule and equipment. You&apos;ll confirm next week&apos;s plan every Sunday/Monday.
            {gyms.length > 1 && (
              <span className="mt-2 block">If you don&apos;t select a specific gym for a slot, the planner will choose the best one based on available equipment.</span>
            )}
          </div>
          {/* Grid header */}
          <div className="grid grid-cols-[2.25rem_1fr_1fr_1fr] gap-1.5 text-center">
            <div />
            {SLOTS.map((s) => (
              <p key={s.key} className="text-xs font-medium text-muted-foreground">
                {s.label}
              </p>
            ))}
          </div>

          {/* Grid rows.
              A286 (C3) — i selettori Home/Gym/Other stavano DENTRO la colonna
              dello slot: 63 bersagli alti ~19px con testo a 10px, sotto il
              minimo WCAG 2.2 e impossibili da centrare col pollice. Nella
              griglia resta solo il toggle del giorno (44px); il dettaglio di
              ogni slot attivo scende sotto, a piena larghezza, dove i tre
              bottoni hanno ~110px ciascuno anche su un 375px. */}
          {WEEKDAYS.map((day) => {
            const activeSlots = SLOTS.filter((slot) => {
              const s = getSlot(day.key, slot.key);
              return s.available || s.preferred_location === "other_sport";
            });
            return (
              <div key={day.key} className="space-y-1.5">
                <div className="grid grid-cols-[2.25rem_1fr_1fr_1fr] gap-1.5 items-center">
                  <p className="text-sm font-medium">{day.label}</p>
                  {SLOTS.map((slot) => {
                    const s = getSlot(day.key, slot.key);
                    const on = s.available || s.preferred_location === "other_sport";
                    return (
                      <button
                        key={slot.key}
                        type="button"
                        aria-pressed={on}
                        aria-label={`${day.label} ${slot.label}`}
                        className={`min-h-[44px] w-full rounded-md border px-2 text-xs transition-colors ${
                          on
                            ? "border-primary bg-primary/10 text-primary font-medium"
                            : "border-border bg-muted/30 text-muted-foreground hover:border-primary/40"
                        }`}
                        onClick={() => {
                          if (s.preferred_location === "other_sport") {
                            updateSlot(day.key, slot.key, { available: false, preferred_location: "home" });
                          } else {
                            toggleSlot(day.key, slot.key);
                          }
                        }}
                      >
                        {s.preferred_location === "other_sport" ? "Other" : s.available ? "Yes" : "–"}
                      </button>
                    );
                  })}
                </div>

                {activeSlots.map((slot) => {
                  const s = getSlot(day.key, slot.key);
                  return (
                    <div
                      key={`${day.key}-${slot.key}-detail`}
                      className="space-y-2 rounded-md border border-border bg-muted/20 p-2.5"
                    >
                      <p className="text-xs font-medium text-muted-foreground">
                        {day.label} · {slot.label}
                      </p>
                      <div className="grid grid-cols-3 gap-1.5">
                        <button
                          type="button"
                          aria-pressed={s.preferred_location === "home"}
                          className={`min-h-[44px] rounded-md border px-2 text-xs font-medium transition-colors ${
                            s.preferred_location === "home"
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border text-muted-foreground"
                          }`}
                          onClick={() => setLocation(day.key, slot.key, "home")}
                        >
                          Home
                        </button>
                        <button
                          type="button"
                          disabled={gyms.length === 0}
                          aria-pressed={s.preferred_location === "gym"}
                          className={`min-h-[44px] rounded-md border px-2 text-xs font-medium transition-colors ${
                            gyms.length === 0
                              ? "border-border text-muted-foreground/40 cursor-not-allowed"
                              : s.preferred_location === "gym"
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-border text-muted-foreground"
                          }`}
                          onClick={() => setLocation(day.key, slot.key, "gym")}
                        >
                          Gym
                        </button>
                        <button
                          type="button"
                          aria-pressed={s.preferred_location === "other_sport"}
                          className={`min-h-[44px] rounded-md border px-2 text-xs font-medium transition-colors ${
                            s.preferred_location === "other_sport"
                              ? "border-warning bg-warning/10 text-warning"
                              : "border-border text-muted-foreground"
                          }`}
                          onClick={() => setLocation(day.key, slot.key, "other_sport")}
                        >
                          Other
                        </button>
                      </div>

                      {/* gym selector or nothing — no-gym banner is shown at page level.
                          B303: only offer a choice when there's more than one gym;
                          with a single gym the planner already defaults to it, so a
                          "Which?" dropdown with one option is pure noise. */}
                      {s.preferred_location === "gym" && gyms.length > 1 && (
                        <Select
                          value={s.gym_id ?? ""}
                          onValueChange={(v) => setGymId(day.key, slot.key, v)}
                        >
                          <SelectTrigger className="min-h-[44px] w-full text-sm">
                            <SelectValue placeholder="Which gym?" />
                          </SelectTrigger>
                          <SelectContent>
                            {gyms.map((g, i) => (
                              <SelectItem
                                key={g.gym_id || i}
                                value={g.gym_id || ""}
                              >
                                {g.name || `Gym ${i + 1}`}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}

                      {s.preferred_location === "other_sport" && (
                        <div className="space-y-2">
                          <Input
                            placeholder="e.g. Circus, Running"
                            className="min-h-[44px]"
                            value={s.other_activity_name ?? ""}
                            onChange={(e) =>
                              updateSlot(day.key, slot.key, { ...s, other_activity_name: e.target.value })
                            }
                          />
                          <div className="flex min-h-[44px] items-center gap-2">
                            <Switch
                              id={`reduce-${day.key}-${slot.key}`}
                              checked={s.reduce_intensity_after ?? false}
                              onCheckedChange={(v) =>
                                updateSlot(day.key, slot.key, { ...s, reduce_intensity_after: v })
                              }
                            />
                            <Label htmlFor={`reduce-${day.key}-${slot.key}`} className="text-xs">
                              Reduce next day
                            </Label>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}

          <p className="text-sm font-medium text-center text-muted-foreground">
            {availableDays} {availableDays === 1 ? "day" : "days"} with availability
          </p>

          <div className="space-y-1 text-xs text-muted-foreground">
            <p><strong>Other</strong> — other activities (sports, circus, etc.) block this slot from climbing training and help calculate your total weekly training load.</p>
            <p><strong>Reduce next day</strong> — enable if this activity is physically demanding. We&apos;ll lower the intensity of your next climbing session.</p>
          </div>
        </CardContent>
      </Card>

      {/* Planning preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Training volume</CardTitle>
          <CardDescription>
            Hard sessions: max hang, limit bouldering, power training, projecting
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>How many days do you want to train per week?</Label>
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
                setPlanningPref("target_training_days_per_week", v)
              }
            />
            {planningPrefs.target_training_days_per_week === 7 && (
              <p className="text-xs text-warning">
                No rest days — not recommended
              </p>
            )}
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Maximum hard sessions per week?</Label>
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
                setPlanningPref("hard_day_cap_per_week", v)
              }
            />
          </div>
        </CardContent>
      </Card>

      <StepNav
        backHref="/onboarding/locations"
        nextHref="/onboarding/trips"
        blockers={availabilityBlockers}
      />
    </div>
  );
}
