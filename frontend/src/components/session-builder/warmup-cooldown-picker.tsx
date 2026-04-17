"use client";

import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { useBuilderBlocks } from "@/lib/hooks/queries";
import type { CustomSessionExercise } from "@/lib/types";

interface WarmupCooldownPickerProps {
  type: "warmup" | "cooldown";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (exercises: Array<{ exercise: CustomSessionExercise; name: string }>) => void;
}

export function WarmupCooldownPicker({ type, open, onOpenChange, onSelect }: WarmupCooldownPickerProps) {
  const { data, isLoading } = useBuilderBlocks();
  const blocks = data?.[type] ?? [];

  const handleSelect = (blockIndex: number) => {
    const block = blocks[blockIndex];
    if (!block) return;
    const exercises = block.exercises.map((ex) => ({
      exercise: {
        exercise_id: ex.exercise_id,
        sets: ex.sets,
        reps: ex.reps,
        work_seconds: ex.work_seconds,
        rest_between_sets_seconds: ex.rest_between_sets_seconds,
        rest_between_reps_seconds: ex.rest_between_reps_seconds,
        load_kg: ex.load_kg,
        notes: ex.notes,
      },
      name: ex.name,
    }));
    onSelect(exercises);
    onOpenChange(false);
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>
            {type === "warmup" ? "Choose Warmup" : "Choose Cooldown"}
          </DrawerTitle>
        </DrawerHeader>

        <div className="px-4 pb-4 space-y-2">
          {isLoading && (
            <p className="text-sm text-muted-foreground text-center py-4">Loading...</p>
          )}
          {blocks.map((block, i) => (
            <button
              key={block.template_id}
              type="button"
              className="w-full rounded-lg border p-4 text-left transition-colors hover:bg-muted/50"
              onClick={() => handleSelect(i)}
            >
              <p className="text-sm font-medium">{block.label}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {block.exercises.length} exercises
              </p>
            </button>
          ))}
          {!isLoading && blocks.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No {type} templates available
            </p>
          )}
        </div>

        <DrawerFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
