"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
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
  { key: "mon", label: "Lun" },
  { key: "tue", label: "Mar" },
  { key: "wed", label: "Mer" },
  { key: "thu", label: "Gio" },
  { key: "fri", label: "Ven" },
  { key: "sat", label: "Sab" },
  { key: "sun", label: "Dom" },
];

const SLOTS = [
  { key: "morning", label: "Mattina" },
  { key: "lunch", label: "Pranzo" },
  { key: "evening", label: "Sera" },
];

type SlotData = { available: boolean; preferred_location: string; gym_id?: string };

export default function AvailabilityPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const availability = data.availability;
  const planningPrefs = data.planning_prefs;
  const gyms = data.equipment.gyms;

  const getSlot = (day: string, slot: string): SlotData => {
    return availability[day]?.[slot] ?? { available: false, preferred_location: "home" };
  };

  const setSlot = (day: string, slot: string, value: SlotData) => {
    const dayData = { ...(availability[day] ?? {}), [slot]: value };
    update("availability", { ...availability, [day]: dayData });
  };

  const toggleSlot = (day: string, slot: string) => {
    const current = getSlot(day, slot);
    setSlot(day, slot, {
      available: !current.available,
      preferred_location: current.preferred_location || "home",
      gym_id: current.gym_id,
    });
  };

  const setLocation = (day: string, slot: string, location: string) => {
    const current = getSlot(day, slot);
    setSlot(day, slot, {
      ...current,
      preferred_location: location,
      gym_id: location === "home" ? undefined : current.gym_id,
    });
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

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Quando ti alleni?</CardTitle>
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
                      {s.available ? "Si" : "-"}
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
                            onClick={() =>
                              setLocation(day.key, slot.key, "home")
                            }
                          >
                            Casa
                          </button>
                          <button
                            type="button"
                            className={`flex-1 rounded text-[10px] px-1 py-0.5 border ${
                              s.preferred_location === "gym"
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-muted text-muted-foreground"
                            }`}
                            onClick={() =>
                              setLocation(day.key, slot.key, "gym")
                            }
                          >
                            Palestra
                          </button>
                        </div>

                        {s.preferred_location === "gym" && gyms.length > 0 && (
                          <Select
                            value={s.gym_id ?? ""}
                            onValueChange={(v) =>
                              setGymId(day.key, slot.key, v)
                            }
                          >
                            <SelectTrigger className="h-6 text-[10px] w-full">
                              <SelectValue placeholder="Quale?" />
                            </SelectTrigger>
                            <SelectContent>
                              {gyms.map((g, i) => (
                                <SelectItem
                                  key={i}
                                  value={g.name || `gym-${i}`}
                                >
                                  {g.name || `Palestra ${i + 1}`}
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
        <CardHeader>
          <CardTitle className="text-lg">Preferenze di allenamento</CardTitle>
          <CardDescription>
            Le sessioni dure includono max hang, boulder al limite, power
            training
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Quanti giorni vuoi allenarti a settimana?</Label>
              <span className="text-sm font-medium tabular-nums">
                {planningPrefs.target_training_days_per_week}
              </span>
            </div>
            <Slider
              min={3}
              max={6}
              step={1}
              value={[planningPrefs.target_training_days_per_week]}
              onValueChange={([v]) =>
                setPlanningPref("target_training_days_per_week", v)
              }
            />
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Massimo sessioni dure per settimana?</Label>
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
                setPlanningPref("hard_day_cap_per_week", v)
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/locations")}
        >
          Indietro
        </Button>
        <Button onClick={() => router.push("/onboarding/trips")}>
          Avanti
        </Button>
      </div>
    </div>
  );
}
