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
  key: string;
  title: string;
  description: string;
  fieldKey: string;
  fieldLabel: string;
  example: string;
  unit: string;
  /** If set, this section is only shown for this device */
  device?: "hangboard" | "loading_pin";
  /** If true, this section uses dual-hand inputs */
  dualHand?: boolean;
  fieldKeyRight?: string;
  fieldKeyLeft?: string;
}

function buildTestSections(device: "hangboard" | "loading_pin"): TestSection[] {
  const sections: TestSection[] = [];

  if (device === "hangboard") {
    sections.push({
      key: "max_hang",
      title: "Max Hang 20mm / 7 seconds",
      description:
        "Hang on a 20mm edge for 7 seconds with the maximum possible weight (half crimp). Include your body weight in the total.",
      fieldKey: "max_hang_20mm_7s_total_kg",
      fieldLabel: "Total load (kg)",
      example: "E.g.: weigh 77kg + 48kg added = 125kg total",
      unit: "kg",
      device: "hangboard",
    });
  } else {
    sections.push({
      key: "lp_max_lift",
      title: "Loading Pin Max Lift (7s)",
      description:
        "Find the heaviest load you can hold for 7 seconds on a 20mm edge block with half crimp. Test each hand separately — external load only (do not add bodyweight).",
      fieldKey: "lp_max_lift_5s_right_kg",
      fieldLabel: "Max lift (kg)",
      example: "E.g.: 45 kg right, 42 kg left",
      unit: "kg",
      device: "loading_pin",
      dualHand: true,
      fieldKeyRight: "lp_max_lift_5s_right_kg",
      fieldKeyLeft: "lp_max_lift_5s_left_kg",
    });
  }

  sections.push(
    {
      key: "weighted_pullup",
      title: "Weighted Pull-up 2RM",
      description:
        "The maximum weight you can complete two full pull-ups with (strict form).",
      fieldKey: "weighted_pullup_1rm_total_kg",
      fieldLabel: "Total load (kg)",
      example: "E.g.: weigh 77kg + 45kg = 122kg total",
      unit: "kg",
    },
    {
      key: "repeater",
      title: "Repeater 7/3 (20mm edge)",
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
  );

  return sections;
}

export default function TestsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const tests = data.tests;
  const device = data.preferences.finger_training_device;

  const sections = buildTestSections(device);

  const [enabled, setEnabled] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const s of sections) {
      if (s.dualHand) {
        init[s.key] =
          tests[s.fieldKeyRight as keyof typeof tests] != null ||
          tests[s.fieldKeyLeft as keyof typeof tests] != null;
      } else {
        init[s.key] = tests[s.fieldKey as keyof typeof tests] != null;
      }
    }
    return init;
  });

  const toggleTest = (key: string, section: TestSection, checked: boolean) => {
    setEnabled((prev) => ({ ...prev, [key]: checked }));
    if (!checked) {
      const cleared = { ...tests };
      if (section.dualHand) {
        (cleared as Record<string, unknown>)[section.fieldKeyRight!] = undefined;
        (cleared as Record<string, unknown>)[section.fieldKeyLeft!] = undefined;
      } else {
        (cleared as Record<string, unknown>)[section.fieldKey] = undefined;
      }
      update("tests", cleared);
    }
  };

  const setField = (fieldKey: string, value: string) => {
    const num = value === "" ? undefined : Number(value);
    update("tests", { ...tests, [fieldKey]: num });
  };

  const setDate = (value: string) => {
    update("tests", { ...tests, last_test_date: value || undefined });
  };

  const setDevice = (dev: "hangboard" | "loading_pin") => {
    update("preferences", { finger_training_device: dev });
    // Clear device-specific test data when switching
    const cleared = { ...tests };
    if (dev === "loading_pin") {
      cleared.max_hang_20mm_7s_total_kg = undefined;
      cleared.max_hang_20mm_5s_total_kg = undefined;
    } else {
      cleared.lp_max_lift_5s_right_kg = undefined;
      cleared.lp_max_lift_5s_left_kg = undefined;
    }
    update("tests", cleared);
    // Reset enabled states for finger-strength tests
    setEnabled((prev) => ({
      ...prev,
      max_hang: false,
      lp_max_lift: false,
    }));
  };

  const anyEnabled = Object.values(enabled).some(Boolean);

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      {/* Device selector */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Finger training device</CardTitle>
          <CardDescription>
            Which device do you primarily use for finger strength training?
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Button
              variant={device === "hangboard" ? "default" : "outline"}
              className="flex-1"
              onClick={() => setDevice("hangboard")}
            >
              Hangboard
            </Button>
            <Button
              variant={device === "loading_pin" ? "default" : "outline"}
              className="flex-1"
              onClick={() => setDevice("loading_pin")}
            >
              Loading Pin
            </Button>
          </div>
          {device === "loading_pin" && (
            <p className="mt-3 text-xs text-muted-foreground">
              The loading pin isolates finger strength without shoulder stress.
              All finger exercises will use your selected device.
              You can change this later in Settings.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Test data */}
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            Do you have test data? (optional but recommended)
          </CardTitle>
          <CardDescription>
            If you&apos;ve done these tests, enter the results. They will significantly
            improve the accuracy of your profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-md border border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-600 dark:bg-blue-950 dark:text-blue-200">
            Accurate test data helps climb-agent build a plan tailored to your specific strengths and weaknesses. After onboarding, we&apos;ll offer a dedicated test week to establish or refresh baselines.
          </div>
          {sections.map((section) => (
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
                      toggleTest(section.key, section, checked)
                    }
                  />
                </div>
              </div>

              {enabled[section.key] && (
                <div className="space-y-3 pt-2">
                  <p className="text-xs text-muted-foreground">
                    {section.description}
                  </p>
                  {section.dualHand ? (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor={`field-${section.key}-right`}>
                          Right hand (kg)
                        </Label>
                        <Input
                          id={`field-${section.key}-right`}
                          type="number"
                          min={0}
                          step={0.5}
                          value={tests[section.fieldKeyRight as keyof typeof tests] ?? ""}
                          onChange={(e) => setField(section.fieldKeyRight!, e.target.value)}
                          placeholder="e.g. 45"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`field-${section.key}-left`}>
                          Left hand (kg)
                        </Label>
                        <Input
                          id={`field-${section.key}-left`}
                          type="number"
                          min={0}
                          step={0.5}
                          value={tests[section.fieldKeyLeft as keyof typeof tests] ?? ""}
                          onChange={(e) => setField(section.fieldKeyLeft!, e.target.value)}
                          placeholder="e.g. 42"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label htmlFor={`field-${section.key}`}>
                        {section.fieldLabel}
                      </Label>
                      <Input
                        id={`field-${section.key}`}
                        type="number"
                        min={0}
                        step={section.unit === "kg" ? 0.5 : 1}
                        value={tests[section.fieldKey as keyof typeof tests] ?? ""}
                        onChange={(e) => setField(section.fieldKey, e.target.value)}
                        placeholder={section.example}
                      />
                      <p className="text-xs text-muted-foreground">
                        {section.example}
                      </p>
                    </div>
                  )}
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
