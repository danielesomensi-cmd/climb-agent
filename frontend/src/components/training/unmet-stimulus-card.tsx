"use client";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

/**
 * B361 — quello che il planner non è riuscito a piazzare, detto all'atleta.
 *
 * `unmet_stimulus` esiste dal [[B308]], che l'ha aggiunto *contro il silenzio*
 * («silence is what let D263 hide for months»); [[B346]] ha aggiunto un
 * `logger.warning` come minimo sindacale. Ma nessun componente lo leggeva: una
 * settimana senza la garanzia di frequenza sulla tirata usciva identica a una
 * settimana normale, e l'unica traccia finiva nei log di Railway.
 *
 * Il tono è deliberatamente informativo e non allarmistico: non è un errore, è
 * il motore che dice di aver dovuto scegliere fra due vincoli. Nella quasi
 * totalità dei casi la causa è che il tetto dei giorni duri o i tempi di
 * recupero non lasciavano spazio — cioè il piano sta proteggendo il recupero,
 * che è il comportamento giusto, non un guasto.
 */
export function UnmetStimulusCard({
  items,
}: {
  items?: Array<{ stimulus: string; phase_id?: string; reason: string }>;
}) {
  if (!items || items.length === 0) return null;

  const names = Array.from(new Set(items.map((i) => i.stimulus)));

  return (
    <Card className="border-warning/30 bg-warning/10">
      <CardContent className="flex gap-3 py-3">
        <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-warning">
            {names.length === 1
              ? `No room for ${names[0]} this week`
              : `Some work didn't fit this week: ${names.join(", ")}`}
          </p>
          <p className="text-xs text-muted-foreground">
            The planner could not fit it without breaking your hard-day cap or the
            recovery gaps between sessions — so it left it out rather than stack
            it on a day that needed rest. Freeing up a slot, or adding a day, is
            usually enough.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
