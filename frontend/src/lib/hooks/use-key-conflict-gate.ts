"use client";

import { useCallback, useState } from "react";
import { blockingConflicts } from "@/lib/key-sessions";
import type { KeyConflict } from "@/lib/types";

/**
 * A294 — run an insertion only after the key-session dry run says it is safe,
 * or after the user confirmed the warning (never a block, decision 2026-10-04).
 *
 * `gate(check, proceed)`: `check` returns the dry-run conflicts (fail-open: an
 * error must resolve to []), `proceed` performs the real write. Render
 * `<KeyConflictDialog {...dialogProps} />` once in the page.
 */
export function useKeyConflictGate() {
  const [pending, setPending] = useState<{ conflicts: KeyConflict[]; proceed: () => void } | null>(null);

  const gate = useCallback(
    async (check: () => Promise<KeyConflict[]>, proceed: () => Promise<void> | void) => {
      let conflicts: KeyConflict[] = [];
      try {
        conflicts = blockingConflicts(await check());
      } catch {
        conflicts = [];
      }
      if (conflicts.length === 0) {
        await proceed();
        return;
      }
      setPending({
        conflicts,
        proceed: () => {
          setPending(null);
          void proceed();
        },
      });
    },
    [],
  );

  const dialogProps = {
    conflicts: pending?.conflicts ?? null,
    onCancel: () => setPending(null),
    onConfirm: () => pending?.proceed(),
  };
  return { gate, dialogProps };
}
