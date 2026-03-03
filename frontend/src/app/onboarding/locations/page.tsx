"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { getOnboardingDefaults } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface EquipmentItem {
  id: string;
  label: string;
  description: string;
}

export default function LocationsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const equipment = data.equipment;
  const outdoorSpots = data.outdoor_spots;

  const [homeEquipment, setHomeEquipment] = useState<EquipmentItem[]>([]);
  const [gymEquipment, setGymEquipment] = useState<EquipmentItem[]>([]);
  const [loadingDefaults, setLoadingDefaults] = useState(true);
  const [newSpotName, setNewSpotName] = useState("");
  const [newSpotDiscipline, setNewSpotDiscipline] = useState<"lead" | "boulder" | "both">("boulder");

  useEffect(() => {
    getOnboardingDefaults()
      .then((defaults) => {
        setHomeEquipment(defaults.equipment_home as EquipmentItem[]);
        setGymEquipment(defaults.equipment_gym as EquipmentItem[]);
      })
      .catch(() => {
        // Silently fail — lists will be empty, user can still proceed
      })
      .finally(() => setLoadingDefaults(false));
  }, []);

  const toggleHomeEnabled = (checked: boolean) => {
    update("equipment", { ...equipment, home_enabled: checked });
  };

  const toggleHomeItem = (id: string, checked: boolean) => {
    const next = checked
      ? [...equipment.home, id]
      : equipment.home.filter((item) => item !== id);
    update("equipment", { ...equipment, home: next });
  };

  const addGym = () => {
    const nextIndex = equipment.gyms.length + 1;
    update("equipment", {
      ...equipment,
      gyms: [...equipment.gyms, { name: `Gym ${nextIndex}`, equipment: [] }],
    });
  };

  const removeGym = (index: number) => {
    update("equipment", {
      ...equipment,
      gyms: equipment.gyms.filter((_, i) => i !== index),
    });
  };

  const setGymName = (index: number, name: string) => {
    const gyms = equipment.gyms.map((g, i) =>
      i === index ? { ...g, name } : g,
    );
    update("equipment", { ...equipment, gyms });
  };

  const toggleGymEquipment = (
    gymIndex: number,
    eqId: string,
    checked: boolean,
  ) => {
    const gyms = equipment.gyms.map((g, i) => {
      if (i !== gymIndex) return g;
      const eqList = checked
        ? [...g.equipment, eqId]
        : g.equipment.filter((item) => item !== eqId);
      return { ...g, equipment: eqList };
    });
    update("equipment", { ...equipment, gyms });
  };

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      {/* Home section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Where do you train?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-3">
            <Switch
              id="home-enabled"
              checked={equipment.home_enabled}
              onCheckedChange={toggleHomeEnabled}
            />
            <Label htmlFor="home-enabled">I train at home</Label>
          </div>

          {equipment.home_enabled && (
            <div className="space-y-4">
              {loadingDefaults ? (
                <div className="flex justify-center py-4">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {homeEquipment.map((item) => (
                    <label
                      key={item.id}
                      className="flex items-start gap-2 cursor-pointer"
                    >
                      <Checkbox
                        checked={equipment.home.includes(item.id)}
                        onCheckedChange={(checked) =>
                          toggleHomeItem(item.id, checked === true)
                        }
                        className="mt-0.5"
                      />
                      <div>
                        <p className="text-sm font-medium leading-tight">
                          {item.label}
                        </p>
                        {item.description && (
                          <p className="text-xs text-muted-foreground">
                            {item.description}
                          </p>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              )}

              <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
                A hangboard is essential for finger training
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gyms section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Gyms</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {equipment.gyms.map((gym, gymIndex) => (
            <div key={gymIndex} className="space-y-4 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">Gym {gymIndex + 1}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  onClick={() => removeGym(gymIndex)}
                >
                  Remove
                </Button>
              </div>

              <div className="space-y-2">
                <Label htmlFor={`gym-name-${gymIndex}`}>Gym name</Label>
                <Input
                  id={`gym-name-${gymIndex}`}
                  value={gym.name}
                  onChange={(e) => setGymName(gymIndex, e.target.value)}
                  placeholder="E.g.: My Climbing Gym"
                />
              </div>

              {loadingDefaults ? (
                <div className="flex justify-center py-4">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {gymEquipment.map((item) => (
                    <label
                      key={item.id}
                      className="flex items-start gap-2 cursor-pointer"
                    >
                      <Checkbox
                        checked={gym.equipment.includes(item.id)}
                        onCheckedChange={(checked) =>
                          toggleGymEquipment(gymIndex, item.id, checked === true)
                        }
                        className="mt-0.5"
                      />
                      <p className="text-sm font-medium leading-tight">
                        {item.label}
                      </p>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}

          <Button variant="outline" className="w-full" onClick={addGym}>
            Add gym
          </Button>

          {equipment.gyms.some((g) => !g.name.trim()) && (
            <p className="text-xs text-red-500">
              All gyms must have a name
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            At least one climbing area is required for climbing sessions
          </p>
        </CardContent>
      </Card>

      {/* Outdoor Spots section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Outdoor Spots</CardTitle>
          <p className="text-xs text-muted-foreground">
            Optional — you can add these later in Settings
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {outdoorSpots.map((spot, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between rounded-md border px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{spot.name}</span>
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {spot.discipline}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive text-xs"
                onClick={() =>
                  update(
                    "outdoor_spots",
                    outdoorSpots.filter((_, i) => i !== idx),
                  )
                }
              >
                Remove
              </Button>
            </div>
          ))}

          <div className="flex gap-2">
            <Input
              placeholder="Spot name"
              value={newSpotName}
              onChange={(e) => setNewSpotName(e.target.value)}
              className="flex-1"
            />
            <select
              value={newSpotDiscipline}
              onChange={(e) =>
                setNewSpotDiscipline(e.target.value as "lead" | "boulder" | "both")
              }
              className="rounded-md border bg-background px-2 py-1 text-sm"
            >
              <option value="boulder">Boulder</option>
              <option value="lead">Lead</option>
              <option value="both">Both</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              disabled={!newSpotName.trim()}
              onClick={() => {
                update("outdoor_spots", [
                  ...outdoorSpots,
                  { name: newSpotName.trim(), discipline: newSpotDiscipline },
                ]);
                setNewSpotName("");
              }}
            >
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/limitations")}
        >
          Back
        </Button>
        <Button
          disabled={equipment.gyms.some((g) => !g.name.trim())}
          onClick={() => router.push("/onboarding/availability")}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
