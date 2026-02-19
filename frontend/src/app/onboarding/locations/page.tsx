"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
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

const HOME_EQUIPMENT: EquipmentItem[] = [
  { id: "hangboard", label: "Hangboard", description: "Finger training board" },
  { id: "pullup_bar", label: "Pull-up bar", description: "" },
  { id: "band", label: "Assistance band", description: "" },
  { id: "dumbbell", label: "Dumbbells", description: "" },
  { id: "kettlebell", label: "Kettlebell", description: "" },
  { id: "ab_wheel", label: "Ab Wheel", description: "" },
  { id: "rings", label: "Rings", description: "" },
  { id: "foam_roller", label: "Foam Roller", description: "" },
  { id: "resistance_band", label: "Resistance band", description: "" },
  { id: "pinch_block", label: "Pinch Block", description: "" },
];

const GYM_EQUIPMENT: EquipmentItem[] = [
  { id: "gym_boulder", label: "Bouldering area", description: "" },
  { id: "gym_routes", label: "Lead / Top-rope walls", description: "" },
  { id: "spraywall", label: "Spraywall", description: "" },
  { id: "board_kilter", label: "Kilter Board", description: "" },
  { id: "board_moonboard", label: "MoonBoard", description: "" },
  { id: "campus_board", label: "Campus Board", description: "" },
  { id: "hangboard", label: "Hangboard", description: "" },
  { id: "dumbbell", label: "Dumbbells", description: "" },
  { id: "barbell", label: "Barbell", description: "" },
  { id: "bench", label: "Bench", description: "" },
  { id: "cable_machine", label: "Cable machine", description: "" },
  { id: "leg_press", label: "Leg press", description: "" },
];

export default function LocationsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const equipment = data.equipment;

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
              <div className="grid grid-cols-2 gap-3">
                {HOME_EQUIPMENT.map((item) => (
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

              <div className="grid grid-cols-2 gap-3">
                {GYM_EQUIPMENT.map((item) => (
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
