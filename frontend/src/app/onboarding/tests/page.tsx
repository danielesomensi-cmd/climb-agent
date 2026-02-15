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
  key: "max_hang" | "weighted_pullup" | "repeater";
  title: string;
  description: string;
  fieldKey: "max_hang_20mm_5s_total_kg" | "weighted_pullup_1rm_total_kg" | "repeater_7_3_max_sets_20mm";
  fieldLabel: string;
  example: string;
  unit: string;
}

const TEST_SECTIONS: TestSection[] = [
  {
    key: "max_hang",
    title: "Max Hang 20mm/5s",
    description:
      "Appendi a un listello da 20mm per 5 secondi con il massimo peso possibile (half crimp). Includi il tuo peso corporeo nel totale.",
    fieldKey: "max_hang_20mm_5s_total_kg",
    fieldLabel: "Carico totale (kg)",
    example: "Es: pesi 77kg + 48kg zavorra = 125kg totale",
    unit: "kg",
  },
  {
    key: "weighted_pullup",
    title: "Weighted Pull-up 1RM",
    description:
      "Il massimo peso con cui riesci a fare una trazione completa.",
    fieldKey: "weighted_pullup_1rm_total_kg",
    fieldLabel: "Carico totale (kg)",
    example: "Es: pesi 77kg + 45kg = 122kg totale",
    unit: "kg",
  },
  {
    key: "repeater",
    title: "Repeater 7/3",
    description:
      "Appendi 7s, riposa 3s, ripeti fino a cedimento al 60% del max hang.",
    fieldKey: "repeater_7_3_max_sets_20mm",
    fieldLabel: "Ripetizioni",
    example: "Es: 24 ripetizioni",
    unit: "reps",
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
            Hai dati oggettivi? (opzionale ma consigliato)
          </CardTitle>
          <CardDescription>
            Se hai fatto questi test, inserisci i risultati. Miglioreranno
            significativamente la precisione del tuo profilo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {TEST_SECTIONS.map((section) => (
            <div key={section.key} className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{section.title}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Label htmlFor={`switch-${section.key}`} className="text-xs text-muted-foreground">
                    Ho questo dato
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
                      step={section.unit === "reps" ? 1 : 0.5}
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
                Quando hai fatto i test?
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
          Indietro
        </Button>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={() => {
              update("tests", {});
              router.push("/onboarding/limitations");
            }}
          >
            Salta
          </Button>
          <Button onClick={() => router.push("/onboarding/limitations")}>
            Avanti
          </Button>
        </div>
      </div>
    </div>
  );
}
