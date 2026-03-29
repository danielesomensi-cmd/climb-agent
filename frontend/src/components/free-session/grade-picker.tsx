"use client";

import { useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";

const FONT_GRADES = [
  "4A", "4B", "4C",
  "5A", "5A+", "5B", "5B+", "5C", "5C+",
  "6A", "6A+", "6B", "6B+", "6C", "6C+",
  "7A", "7A+", "7B", "7B+", "7C", "7C+",
  "8A", "8A+", "8B", "8B+", "8C", "8C+",
];

interface GradePickerProps {
  value: string;
  onChange: (grade: string) => void;
  gradeSystem?: BoulderGradeSystem;
}

export function GradePicker({ value, onChange, gradeSystem = "font" }: GradePickerProps) {
  const currentIndex = FONT_GRADES.indexOf(value.toUpperCase());
  const idx = currentIndex >= 0 ? currentIndex : 9; // default 6A

  const prev = useCallback(() => {
    if (idx > 0) onChange(FONT_GRADES[idx - 1]);
  }, [idx, onChange]);

  const next = useCallback(() => {
    if (idx < FONT_GRADES.length - 1) onChange(FONT_GRADES[idx + 1]);
  }, [idx, onChange]);

  const displayGrade = FONT_GRADES[idx] || value;

  return (
    <div className="flex items-center justify-center gap-3">
      <Button
        variant="outline"
        size="icon"
        onClick={prev}
        disabled={idx <= 0}
        className="h-12 w-12 rounded-full"
      >
        <ChevronLeft className="size-6" />
      </Button>
      <span className="min-w-[80px] text-center text-3xl font-bold tabular-nums">
        {displayBoulderGrade(displayGrade, gradeSystem)}
      </span>
      <Button
        variant="outline"
        size="icon"
        onClick={next}
        disabled={idx >= FONT_GRADES.length - 1}
        className="h-12 w-12 rounded-full"
      >
        <ChevronRight className="size-6" />
      </Button>
    </div>
  );
}

export { FONT_GRADES };
