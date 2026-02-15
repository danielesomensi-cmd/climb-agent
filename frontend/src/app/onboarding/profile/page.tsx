"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function ProfilePage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const profile = data.profile;

  const [knowsBf, setKnowsBf] = useState(profile.body_fat_pct != null);

  const set = (field: keyof typeof profile, value: string | number | undefined) => {
    update("profile", { ...profile, [field]: value });
  };

  const isValid =
    profile.name.trim() !== "" &&
    profile.age > 0 &&
    profile.weight_kg > 0 &&
    profile.height_cm > 0;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Your profile</CardTitle>
          <CardDescription>
            Weight is used to calculate relative loads (e.g. weight-to-finger-strength ratio)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={profile.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Your name"
            />
          </div>

          {/* Preferred name */}
          <div className="space-y-2">
            <Label htmlFor="preferred_name">Preferred name</Label>
            <Input
              id="preferred_name"
              value={profile.preferred_name ?? ""}
              onChange={(e) =>
                set("preferred_name", e.target.value || undefined)
              }
              placeholder="Nickname (optional)"
            />
          </div>

          {/* Age */}
          <div className="space-y-2">
            <Label htmlFor="age">Age *</Label>
            <Input
              id="age"
              type="number"
              min={1}
              max={99}
              value={profile.age || ""}
              onChange={(e) => set("age", Number(e.target.value))}
            />
          </div>

          {/* Weight */}
          <div className="space-y-2">
            <Label htmlFor="weight_kg">Weight (kg) *</Label>
            <Input
              id="weight_kg"
              type="number"
              min={1}
              step={0.1}
              value={profile.weight_kg || ""}
              onChange={(e) => set("weight_kg", Number(e.target.value))}
            />
          </div>

          {/* Height */}
          <div className="space-y-2">
            <Label htmlFor="height_cm">Height (cm) *</Label>
            <Input
              id="height_cm"
              type="number"
              min={1}
              value={profile.height_cm || ""}
              onChange={(e) => set("height_cm", Number(e.target.value))}
            />
          </div>

          {/* Body fat */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Switch
                id="knows_bf"
                checked={knowsBf}
                onCheckedChange={(checked) => {
                  setKnowsBf(checked);
                  if (!checked) set("body_fat_pct", undefined);
                }}
              />
              <Label htmlFor="knows_bf">I know my body fat percentage</Label>
            </div>
            {knowsBf && (
              <div className="space-y-2">
                <Label htmlFor="body_fat_pct">Body fat (%)</Label>
                <Input
                  id="body_fat_pct"
                  type="number"
                  min={1}
                  max={50}
                  step={0.1}
                  value={profile.body_fat_pct ?? ""}
                  onChange={(e) =>
                    set("body_fat_pct", e.target.value ? Number(e.target.value) : undefined)
                  }
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/welcome")}
        >
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/experience")}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
