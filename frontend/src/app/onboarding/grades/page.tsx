"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";

const LEAD_GRADES = [
  "5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

const BOULDER_GRADES = [
  "5A","5A+","5B","5B+","5C","5C+",
  "6A","6A+","6B","6B+","6C","6C+",
  "7A","7A+","7B","7B+","7C","7C+",
  "8A","8A+","8B","8B+","8C","8C+",
];

function GradeSelect({
  value,
  onChange,
  options,
  placeholder,
  formatter,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  placeholder: string;
  formatter?: (g: string) => string;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((g) => (
          <SelectItem key={g} value={g}>
            {formatter ? formatter(g) : g}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export default function GradesPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const grades = data.grades;
  const discipline = data.goal.discipline || "lead";
  const gradeSystem = (data.preferences.grade_system_boulder ?? "font") as BoulderGradeSystem;

  const showLead = discipline === "lead" || discipline === "both";
  const showBoulder = discipline === "boulder" || discipline === "both";
  const leadRequired = showLead;
  const boulderRequired = showBoulder;

  const set = (field: keyof typeof grades, value: string) => {
    update("grades", { ...grades, [field]: value });
  };

  const toggleGradeSystem = () => {
    update("preferences", {
      ...data.preferences,
      grade_system_boulder: gradeSystem === "font" ? "v_scale" : "font",
    });
  };

  const formatBoulder = useMemo(
    () => (g: string) => displayBoulderGrade(g, gradeSystem),
    [gradeSystem],
  );

  // Validation: required fields must be filled
  const leadValid = !leadRequired || (grades.lead_max_rp !== "" && grades.lead_max_os !== "");
  const boulderValid = !boulderRequired || ((grades.boulder_max_rp ?? "") !== "" && (grades.boulder_max_os ?? "") !== "");
  const isValid = leadValid && boulderValid;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      {/* Lead grades */}
      {showLead && (
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Lead grades</CardTitle>
            <CardDescription>
              The gap between redpoint and onsight tells us about your power
              endurance and technique
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>Redpoint {leadRequired && "*"}</Label>
              <p className="text-xs text-muted-foreground">
                Your highest grade after working the route
              </p>
              <GradeSelect
                value={grades.lead_max_rp}
                onChange={(v) => set("lead_max_rp", v)}
                options={LEAD_GRADES}
                placeholder="Select grade"
              />
            </div>
            <div className="space-y-2">
              <Label>Onsight {leadRequired && "*"}</Label>
              <p className="text-xs text-muted-foreground">
                The grade you can climb on sight
              </p>
              <GradeSelect
                value={grades.lead_max_os}
                onChange={(v) => set("lead_max_os", v)}
                options={LEAD_GRADES}
                placeholder="Select grade"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Boulder grades */}
      {showBoulder && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-xl">Boulder grades</CardTitle>
              <button
                type="button"
                onClick={toggleGradeSystem}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-md border border-border"
              >
                {gradeSystem === "font" ? "Font" : "V-scale"} ↔
              </button>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>Redpoint {boulderRequired && "*"}</Label>
              <p className="text-xs text-muted-foreground">
                Your maximum boulder grade
              </p>
              <GradeSelect
                value={grades.boulder_max_rp ?? ""}
                onChange={(v) => set("boulder_max_rp", v)}
                options={BOULDER_GRADES}
                placeholder="Select grade"
                formatter={formatBoulder}
              />
            </div>
            <div className="space-y-2">
              <Label>Onsight / Flash {boulderRequired && "*"}</Label>
              <p className="text-xs text-muted-foreground">
                Your boulder onsight or flash grade
              </p>
              <GradeSelect
                value={grades.boulder_max_os ?? ""}
                onChange={(v) => set("boulder_max_os", v)}
                options={BOULDER_GRADES}
                placeholder="Select grade"
                formatter={formatBoulder}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Optional other-discipline grades */}
      {discipline !== "both" && (
        <details className="group">
          <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors">
            {discipline === "lead" ? "Boulder grades" : "Lead grades"} (optional)
          </summary>
          <Card className="mt-3">
            <CardContent className="space-y-5 pt-5">
              {discipline === "lead" ? (
                <>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Boulder Redpoint</Label>
                      <button
                        type="button"
                        onClick={toggleGradeSystem}
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-md border border-border"
                      >
                        {gradeSystem === "font" ? "Font" : "V-scale"} ↔
                      </button>
                    </div>
                    <GradeSelect
                      value={grades.boulder_max_rp ?? ""}
                      onChange={(v) => set("boulder_max_rp", v)}
                      options={BOULDER_GRADES}
                      placeholder="Select grade (optional)"
                      formatter={formatBoulder}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Boulder Onsight / Flash</Label>
                    <GradeSelect
                      value={grades.boulder_max_os ?? ""}
                      onChange={(v) => set("boulder_max_os", v)}
                      options={BOULDER_GRADES}
                      placeholder="Select grade (optional)"
                      formatter={formatBoulder}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>Lead Redpoint</Label>
                    <GradeSelect
                      value={grades.lead_max_rp}
                      onChange={(v) => set("lead_max_rp", v)}
                      options={LEAD_GRADES}
                      placeholder="Select grade (optional)"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Lead Onsight</Label>
                    <GradeSelect
                      value={grades.lead_max_os}
                      onChange={(v) => set("lead_max_os", v)}
                      options={LEAD_GRADES}
                      placeholder="Select grade (optional)"
                    />
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </details>
      )}

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/discipline")}
        >
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/goals")}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
