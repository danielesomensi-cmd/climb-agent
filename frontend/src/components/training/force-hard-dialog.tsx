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

/**
 * A254 — explicit confirm before forcing a hard finger session past the 48h
 * recovery gap. Finger overreach (tendons/pulleys) is the most common climbing
 * injury, so this override is deliberately a two-step decision, not a one-tap
 * toast action (which is fine for a mere weekly-cap downshift).
 */
export function ForceHardDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Add the hard finger session anyway?</AlertDialogTitle>
          <AlertDialogDescription>
            You trained fingers within the last 48h. Your plan eased this session to
            protect tendon and pulley recovery — the most common climbing injury.
            Forcing a second hard finger day now raises that risk. Only do this if
            you&apos;re sure your fingers are ready.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it easy</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Add anyway — I accept the risk
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
