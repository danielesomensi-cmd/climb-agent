"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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

interface ProfileAssessmentEditorProps {
  open: boolean;
  currentAssessment: Record<string, unknown>;
  onConfirm: (patch: Record<string, unknown>) => void;
  onCancel: () => void;
  saving: boolean;
}

export function ProfileAssessmentEditor({
  open,
  currentAssessment,
  onConfirm,
  onCancel,
  saving,
}: ProfileAssessmentEditorProps) {
  const body = (currentAssessment.body ?? {}) as Record<string, number>;
  const grades = (currentAssessment.grades ?? {}) as Record<string, string>;
  const tests = (currentAssessment.tests ?? {}) as Record<string, number | undefined>;

  const [step, setStep] = useState<"form" | "confirm">("form");

  // Body
  const [weightKg, setWeightKg] = useState<string>(body.weight_kg != null ? String(body.weight_kg) : "");
  const [heightCm, setHeightCm] = useState<string>(body.height_cm != null ? String(body.height_cm) : "");

  // Grades
  const [leadMaxRp, setLeadMaxRp] = useState<string>(grades.lead_max_rp ?? "");
  const [leadMaxOs, setLeadMaxOs] = useState<string>(grades.lead_max_os ?? "");
  const [boulderMaxRp, setBoulderMaxRp] = useState<string>(grades.boulder_max_rp ?? "");
  const [boulderMaxOs, setBoulderMaxOs] = useState<string>(grades.boulder_max_os ?? "");

  // Tests (optional)
  const [maxHang, setMaxHang] = useState<string>(tests.max_hang_20mm_5s_total_kg != null ? String(tests.max_hang_20mm_5s_total_kg) : "");
  const [weightedPullup, setWeightedPullup] = useState<string>(tests.weighted_pullup_1rm_total_kg != null ? String(tests.weighted_pullup_1rm_total_kg) : "");
  const [repeater, setRepeater] = useState<string>(tests.repeater_7_3_max_sets_20mm != null ? String(tests.repeater_7_3_max_sets_20mm) : "");

  const isValid = leadMaxRp !== "" && leadMaxOs !== "";

  function buildPatch(): Record<string, unknown> {
    const patch: Record<string, unknown> = {};

    // Body
    const bodyPatch: Record<string, number> = {};
    if (weightKg !== "") bodyPatch.weight_kg = parseFloat(weightKg);
    if (heightCm !== "") bodyPatch.height_cm = parseFloat(heightCm);
    if (Object.keys(bodyPatch).length > 0) patch.body = bodyPatch;

    // Grades
    const gradesPatch: Record<string, string> = { lead_max_rp: leadMaxRp, lead_max_os: leadMaxOs };
    if (boulderMaxRp) gradesPatch.boulder_max_rp = boulderMaxRp;
    if (boulderMaxOs) gradesPatch.boulder_max_os = boulderMaxOs;
    patch.grades = gradesPatch;

    // Tests
    const testsPatch: Record<string, number> = {};
    if (maxHang !== "") testsPatch.max_hang_20mm_5s_total_kg = parseFloat(maxHang);
    if (weightedPullup !== "") testsPatch.weighted_pullup_1rm_total_kg = parseFloat(weightedPullup);
    if (repeater !== "") testsPatch.repeater_7_3_max_sets_20mm = parseFloat(repeater);
    if (Object.keys(testsPatch).length > 0) patch.tests = testsPatch;

    return patch;
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen && !saving) {
      setStep("form");
      onCancel();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        {step === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>Edit profile & assessment</DialogTitle>
              <DialogDescription>
                Update your body metrics, grades, and test results
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6 py-2">
              {/* Body */}
              <div className="space-y-3">
                <p className="text-sm font-semibold">Body</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="pa-weight">Weight (kg)</Label>
                    <Input
                      id="pa-weight"
                      type="number"
                      step="0.5"
                      min="30"
                      max="200"
                      placeholder="e.g. 72"
                      value={weightKg}
                      onChange={(e) => setWeightKg(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pa-height">Height (cm)</Label>
                    <Input
                      id="pa-height"
                      type="number"
                      step="1"
                      min="100"
                      max="250"
                      placeholder="e.g. 175"
                      value={heightCm}
                      onChange={(e) => setHeightCm(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Grades */}
              <div className="space-y-3">
                <p className="text-sm font-semibold">Grades</p>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>Lead RP *</Label>
                      <Select value={leadMaxRp} onValueChange={setLeadMaxRp}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                        <SelectContent>
                          {LEAD_GRADES.map((g) => (
                            <SelectItem key={g} value={g}>{g}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Lead OS *</Label>
                      <Select value={leadMaxOs} onValueChange={setLeadMaxOs}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                        <SelectContent>
                          {LEAD_GRADES.map((g) => (
                            <SelectItem key={g} value={g}>{g}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>Boulder RP</Label>
                      <Select value={boulderMaxRp} onValueChange={setBoulderMaxRp}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Optional" />
                        </SelectTrigger>
                        <SelectContent>
                          {BOULDER_GRADES.map((g) => (
                            <SelectItem key={g} value={g}>{g}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Boulder OS</Label>
                      <Select value={boulderMaxOs} onValueChange={setBoulderMaxOs}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Optional" />
                        </SelectTrigger>
                        <SelectContent>
                          {BOULDER_GRADES.map((g) => (
                            <SelectItem key={g} value={g}>{g}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tests */}
              <div className="space-y-3">
                <p className="text-sm font-semibold">Test results <span className="font-normal text-muted-foreground">(optional)</span></p>
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="pa-maxhang">Max hang 20mm / 5s — total kg</Label>
                    <Input
                      id="pa-maxhang"
                      type="number"
                      step="0.5"
                      placeholder="e.g. 90"
                      value={maxHang}
                      onChange={(e) => setMaxHang(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pa-pullup">Weighted pullup 1RM — total kg</Label>
                    <Input
                      id="pa-pullup"
                      type="number"
                      step="0.5"
                      placeholder="e.g. 100"
                      value={weightedPullup}
                      onChange={(e) => setWeightedPullup(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="pa-repeater">Repeater 7/3 max sets (20mm)</Label>
                    <Input
                      id="pa-repeater"
                      type="number"
                      step="1"
                      min="0"
                      placeholder="e.g. 6"
                      value={repeater}
                      onChange={(e) => setRepeater(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button onClick={() => setStep("confirm")} disabled={!isValid}>
                Save
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Confirm changes</DialogTitle>
              <DialogDescription>
                This will recalculate your assessment profile. Your current training plan will not change unless you regenerate the macrocycle.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("form")} disabled={saving}>
                Back
              </Button>
              <Button onClick={() => onConfirm(buildPatch())} disabled={saving}>
                {saving ? "Saving..." : "Confirm"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
