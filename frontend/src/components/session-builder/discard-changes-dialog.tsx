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
 * B356 — la conferma "scarta modifiche" del session builder.
 *
 * Viveva dentro `SessionBuilder`, aperta da un `handleBack` che nessun pulsante
 * richiamava: l'uscita reale è il chevron della TopBar, che sta nella PAGINA e
 * navigava via senza chiedere niente. Risultato: componevi una sessione, tornavi
 * indietro e perdevi tutto in silenzio. Il dialog vive qui perché ora lo montano
 * le due pagine del builder (nuova e modifica), che sono quelle che possiedono
 * il pulsante.
 */
export function DiscardChangesDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Discard changes?</AlertDialogTitle>
          <AlertDialogDescription>
            You have unsaved changes. Are you sure you want to go back?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Discard</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
