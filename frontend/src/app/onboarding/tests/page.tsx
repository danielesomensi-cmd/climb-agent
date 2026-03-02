"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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

interface TestSection {
  key: "max_hang" | "weighted_pullup" | "repeater" | "hang_duration" | "l_sit" | "hip_flex";
  title: string;
  description: string;
  fieldKey: "max_hang_20mm_5s_total_kg" | "weighted_pullup_1rm_total_kg" | "repeater_7_3_max_sets_20mm" | "max_hang_duration_20mm_seconds" | "l_sit_hold_seconds" | "hip_flexibility_cm";
  fieldLabel: string;
  example: string;
  unit: string;
}

const TEST_SECTIONS: TestSection[] = [
  {
    key: "max_hang",
    title: "Max Hang 20mm/5s",
    description:
      "Hang on a 20mm edge for 5 seconds with the maximum possible weight (half crimp). Include your body weight in the total.",
    fieldKey: "max_hang_20mm_5s_total_kg",
    fieldLabel: "Total load (kg)",
    example: "E.g.: weigh 77kg + 48kg added = 125kg total",
    unit: "kg",
  },
  {
    key: "weighted_pullup",
    title: "Weighted Pull-up 1RM",
    description:
      "The maximum weight you can complete one full pull-up with.",
    fieldKey: "weighted_pullup_1rm_total_kg",
    fieldLabel: "Total load (kg)",
    example: "E.g.: weigh 77kg + 45kg = 122kg total",
    unit: "kg",
  },
  {
    key: "repeater",
    title: "Repeater 7/3",
    description:
      "Hang 7s, rest 3s, repeat to failure at 60% of max hang.",
    fieldKey: "repeater_7_3_max_sets_20mm",
    fieldLabel: "Repetitions",
    example: "E.g.: 24 reps",
    unit: "reps",
  },
  {
    key: "hang_duration",
    title: "Max Hang Duration (20mm)",
    description:
      "Hang bodyweight-only on a 20mm edge, half crimp, as long as possible. Stop when you drop.",
    fieldKey: "max_hang_duration_20mm_seconds",
    fieldLabel: "Duration (seconds)",
    example: "E.g.: 65 seconds. Moderate ~45s, advanced 60-90s, elite ~120s",
    unit: "seconds",
  },
  {
    key: "l_sit",
    title: "L-sit Hold",
    description:
      "Hold an L-sit position with straight legs on parallel bars, dip bars, or rings. Time until form breaks.",
    fieldKey: "l_sit_hold_seconds",
    fieldLabel: "Duration (seconds)",
    example: "E.g.: 20 seconds",
    unit: "seconds",
  },
  {
    key: "hip_flex",
    title: "Hip Flexibility (Straddle Split)",
    description:
      "Sit with legs spread as wide as possible, back against wall, knees straight. Measure distance between heels in cm.",
    fieldKey: "hip_flexibility_cm",
    fieldLabel: "Distance (cm)",
    example: "E.g.: 120 cm",
    unit: "cm",
  },
];

export default function TestsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const tests = data.tests;

  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    max_hang: tests.max_hang_20mm_5s_total_kg != null,
    weighted_pullup: tests.weighted_pullup_1rm_total_kg != null,
    repeater: tests.repeater_7_3_max_sets_20mm != null,
    hang_duration: tests.max_hang_duration_20mm_seconds != null,
    l_sit: tests.l_sit_hold_seconds != null,
    hip_flex: tests.hip_flexibility_cm != null,
  });

  const toggleTest = (key: string, fieldKey: TestSection["fieldKey"], checked: boolean) => {
    setEnabled((prev) => ({ ...prev, [key]: checked }));
    if (!checked) {
      update("tests", { ...tests, [fieldKey]: undefined });
    }
  };

  const setField = (fieldKey: TestSection["fieldKey"], value: string) => {
    const num = value === "" ? undefined : Number(value);
    update("tests", { ...tests, [fieldKey]: num });
  };

  const setDate = (value: string) => {
    update("tests", { ...tests, last_test_date: value || undefined });
  };

  const anyEnabled = Object.values(enabled).some(Boolean);

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            Do you have test data? (optional but recommended)
          </CardTitle>
          <CardDescription>
            If you've done these tests, enter the results. They will significantly
            improve the accuracy of your profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-md border border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-600 dark:bg-blue-950 dark:text-blue-200">
            Accurate test data helps climb-agent build a plan tailored to your specific strengths and weaknesses. After onboarding, we&apos;ll offer a dedicated test week to establish or refresh baselines.
          </div>
          {TEST_SECTIONS.map((section) => (
            <div key={section.key} className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{section.title}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Label htmlFor={`switch-${section.key}`} className="text-xs text-muted-foreground">
                    I have this data
                  </Label>
                  <Switch
                    id={`switch-${section.key}`}
                    checked={enabled[section.key]}
                    onCheckedChange={(checked) =>
                      toggleTest(section.key, section.fieldKey, checked)
                    }
                  />
                </div>
              </div>

              {enabled[section.key] && (
                <div className="space-y-3 pt-2">
                  <p className="text-xs text-muted-foreground">
                    {section.description}
                  </p>
                  <div className="space-y-2">
                    <Label htmlFor={`field-${section.key}`}>
                      {section.fieldLabel}
                    </Label>
                    <Input
                      id={`field-${section.key}`}
                      type="number"
                      min={0}
                      step={section.unit === "kg" ? 0.5 : 1}
                      value={tests[section.fieldKey] ?? ""}
                      onChange={(e) => setField(section.fieldKey, e.target.value)}
                      placeholder={section.example}
                    />
                    <p className="text-xs text-muted-foreground">
                      {section.example}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Last test date */}
          {anyEnabled && (
            <div className="space-y-2">
              <Label htmlFor="last_test_date">
                When did you take the tests?
              </Label>
              <Input
                id="last_test_date"
                type="date"
                value={tests.last_test_date ?? ""}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/weaknesses")}
        >
          Back
        </Button>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              update("tests", {});
              router.push("/onboarding/limitations");
            }}
          >
            Skip
          </Button>
          <Button onClick={() => router.push("/onboarding/limitations")}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
