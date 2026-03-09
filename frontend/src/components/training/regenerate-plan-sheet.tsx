"use client";

import { useState } from "react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
  DrawerClose,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type RegenerateStartOption = "today" | "tomorrow" | "next_monday";

interface RegeneratePlanSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (option: RegenerateStartOption) => void;
  loading?: boolean;
}

function getNextMonday(): string {
  const d = new Date();
  const day = d.getDay(); // 0=Sun, 1=Mon, ...
  const diff = day === 0 ? 1 : 8 - day;
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

function getTomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Convert a RegenerateStartOption to a preserve_before date string. */
export function optionToPreserveBefore(option: RegenerateStartOption): string {
  switch (option) {
    case "today":
      return getToday();
    case "tomorrow":
      return getTomorrow();
    case "next_monday":
      return getNextMonday();
  }
}

export function RegeneratePlanSheet({
  open,
  onOpenChange,
  onConfirm,
  loading,
}: RegeneratePlanSheetProps) {
  const [selected, setSelected] = useState<RegenerateStartOption>("tomorrow");

  const options: {
    value: RegenerateStartOption;
    label: string;
    recommended?: boolean;
  }[] = [
    { value: "today", label: "Today" },
    { value: "tomorrow", label: "Tomorrow", recommended: true },
    { value: "next_monday", label: "Next Monday" },
  ];

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Regenerate plan from&hellip;</DrawerTitle>
          <DrawerDescription>
            &ldquo;Tomorrow&rdquo; is recommended &mdash; keeps today&apos;s
            sessions intact.
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex justify-center gap-2 px-4 pb-2">
          {options.map((opt) => (
            <Button
              key={opt.value}
              variant={selected === opt.value ? "default" : "outline"}
              size="sm"
              className={cn(
                "flex-1",
                selected === opt.value && "ring-2 ring-primary ring-offset-2 ring-offset-background"
              )}
              onClick={() => setSelected(opt.value)}
            >
              {opt.label}
              {opt.recommended && selected === opt.value ? " \u2713" : ""}
            </Button>
          ))}
        </div>

        <DrawerFooter>
          <Button
            onClick={() => onConfirm(selected)}
            disabled={loading}
          >
            {loading ? "Processing..." : "Confirm"}
          </Button>
          <DrawerClose asChild>
            <Button variant="outline">Cancel</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
