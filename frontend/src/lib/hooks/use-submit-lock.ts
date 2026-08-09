import { useCallback, useRef, useState } from "react";

/**
 * Runs an async submit handler at most once at a time (B330).
 *
 * `disabled={busy}` on the button is NOT enough on its own: `setState` is
 * asynchronous, so two taps landing in the same React batch both enter the
 * handler before the re-render that disables the button. On a phone that is a
 * very ordinary double tap — and on a slow network the window is the whole
 * request. The guard here is a ref, which flips synchronously on the first
 * call, so the second one returns immediately.
 *
 * Use the returned `busy` for the button's disabled state and label; it tracks
 * the same lock and drives the re-render the ref cannot.
 *
 * `run` re-throws whatever `fn` throws — the hook owns the lock, not the error
 * policy — and releases the lock either way. Callers that pass a handler which
 * can reject should attach a `.catch`, or the rejection lands unhandled.
 */
export function useSubmitLock<A extends unknown[]>(
  fn: (...args: A) => Promise<void>,
): { run: (...args: A) => Promise<void>; busy: boolean } {
  const locked = useRef(false);
  const [busy, setBusy] = useState(false);

  const run = useCallback(
    async (...args: A) => {
      if (locked.current) return;
      locked.current = true;
      setBusy(true);
      try {
        await fn(...args);
      } finally {
        locked.current = false;
        setBusy(false);
      }
    },
    [fn],
  );

  return { run, busy };
}
