"use client";

import { useCallback, useRef, useState } from "react";
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
  const [pending, setPending] = useState<{
    conflicts: KeyConflict[];
    proceed: () => void;
    cancel?: () => void;
  } | null>(null);

  const settled = useRef<unknown>(null);

  const gate = useCallback(
    async (
      check: () => Promise<KeyConflict[]>,
      proceed: () => Promise<void> | void,
      /** A294 review: called when the user backs out of the warning (e.g. to reset a spinner). */
      onCancel?: () => void,
    ) => {
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
      const entry = {
        conflicts,
        proceed: () => {
          // The dialog's action also closes it (onOpenChange → onCancel):
          // once confirmed, that close must not run the cancel callback.
          settled.current = entry;
          setPending(null);
          void proceed();
        },
        cancel: onCancel,
      };
      settled.current = null;
      setPending(entry);
    },
    [],
  );

  const dialogProps = {
    conflicts: pending?.conflicts ?? null,
    onCancel: () => {
      if (pending && settled.current !== pending) pending.cancel?.();
      setPending(null);
    },
    onConfirm: () => pending?.proceed(),
  };
  return { gate, dialogProps };
}
