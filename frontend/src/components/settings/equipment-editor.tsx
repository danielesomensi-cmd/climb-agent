"use client";

import { useEffect, useState } from "react";
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

interface GymData {
  name: string;
  equipment: string[];
}

interface EquipmentEditorProps {
  initialEquipment: {
    home_enabled?: boolean;
    home?: string[];
    gyms?: GymData[];
  };
  onSave: (equipment: Record<string, unknown>) => void;
  onCancel: () => void;
}

export function EquipmentEditor({
  initialEquipment,
  onSave,
  onCancel,
}: EquipmentEditorProps) {
  const [homeEnabled, setHomeEnabled] = useState(initialEquipment.home_enabled ?? false);
  const [home, setHome] = useState<string[]>(initialEquipment.home ?? []);
  const [gyms, setGyms] = useState<GymData[]>(
    () => JSON.parse(JSON.stringify(initialEquipment.gyms ?? [])),
  );

  const [homeOptions, setHomeOptions] = useState<EquipmentItem[]>([]);
  const [gymOptions, setGymOptions] = useState<EquipmentItem[]>([]);
  const [loadingDefaults, setLoadingDefaults] = useState(true);

  useEffect(() => {
    getOnboardingDefaults()
      .then((defaults) => {
        setHomeOptions(defaults.equipment_home as EquipmentItem[]);
        setGymOptions(defaults.equipment_gym as EquipmentItem[]);
      })
      .catch(() => {})
      .finally(() => setLoadingDefaults(false));
  }, []);

  const toggleHomeItem = (id: string, checked: boolean) => {
    setHome((prev) => (checked ? [...prev, id] : prev.filter((x) => x !== id)));
  };

  const addGym = () => {
    setGyms((prev) => [...prev, { name: `Gym ${prev.length + 1}`, equipment: [] }]);
  };

  const removeGym = (index: number) => {
    setGyms((prev) => prev.filter((_, i) => i !== index));
  };

  const setGymName = (index: number, name: string) => {
    setGyms((prev) => prev.map((g, i) => (i === index ? { ...g, name } : g)));
  };

  const toggleGymEquipment = (gymIndex: number, eqId: string, checked: boolean) => {
    setGyms((prev) =>
      prev.map((g, i) => {
        if (i !== gymIndex) return g;
        const eqList = checked
          ? [...g.equipment, eqId]
          : g.equipment.filter((x) => x !== eqId);
        return { ...g, equipment: eqList };
      }),
    );
  };

  const handleSave = () => {
    onSave({
      home_enabled: homeEnabled,
      home: homeEnabled ? home : [],
      gyms,
    });
  };

  const hasEmptyGymName = gyms.some((g) => !g.name.trim());

  return (
    <div className="space-y-4">
      {/* Home section */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Home training</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              id="eq-home-enabled"
              checked={homeEnabled}
              onCheckedChange={setHomeEnabled}
            />
            <Label htmlFor="eq-home-enabled">I train at home</Label>
          </div>

          {homeEnabled && (
            loadingDefaults ? (
              <div className="flex justify-center py-4">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {homeOptions.map((item) => (
                  <label key={item.id} className="flex items-start gap-2 cursor-pointer">
                    <Checkbox
                      checked={home.includes(item.id)}
                      onCheckedChange={(checked) => toggleHomeItem(item.id, checked === true)}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium leading-tight">{item.label}</p>
                      {item.description && (
                        <p className="text-xs text-muted-foreground">{item.description}</p>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )
          )}
        </CardContent>
      </Card>

      {/* Gyms section */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Gyms</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {gyms.map((gym, gymIndex) => (
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
                <Label htmlFor={`eq-gym-name-${gymIndex}`}>Gym name</Label>
                <Input
                  id={`eq-gym-name-${gymIndex}`}
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
                  {gymOptions.map((item) => (
                    <label key={item.id} className="flex items-start gap-2 cursor-pointer">
                      <Checkbox
                        checked={gym.equipment.includes(item.id)}
                        onCheckedChange={(checked) =>
                          toggleGymEquipment(gymIndex, item.id, checked === true)
                        }
                        className="mt-0.5"
                      />
                      <p className="text-sm font-medium leading-tight">{item.label}</p>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}

          <Button variant="outline" className="w-full" onClick={addGym}>
            Add gym
          </Button>

          {hasEmptyGymName && (
            <p className="text-xs text-red-500">All gyms must have a name</p>
          )}
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSave} disabled={hasEmptyGymName}>
          Save
        </Button>
      </div>
    </div>
  );
}
