"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { KeyConflict } from "@/lib/types";

/**
 * A294 — confirm before a custom session takes a key session's place.
 *
 * Decision 2026-10-04: a warning with confirm, never a block. When the custom
 * delivers the same stimulus (`replace_key`), the key is *replaced*, not lost —
 * the copy says so and the confirm is the default action.
 */
export function KeyConflictDialog({
  conflicts,
  onCancel,
  onConfirm,
}: {
  conflicts: KeyConflict[] | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const open = !!conflicts && conflicts.length > 0;
  const onlyReplace = open && conflicts!.every((c) => c.code === "key_replaced");
  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!v) onCancel(); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {onlyReplace ? "This replaces a key session" : "This affects a key session"}
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2 text-sm">
              {(conflicts ?? []).map((c, i) => (
                <p key={`${c.code}-${i}`}>{c.message}</p>
              ))}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Pick another day</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>
            {onlyReplace ? "Replace it" : "Add anyway"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
