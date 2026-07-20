"use client";

import { ErrorFallback } from "@/components/error-fallback";
import "./globals.css";

/**
 * A245 C-4 (F10) — last-resort boundary. Catches errors thrown in the root
 * layout itself, which the per-segment error.tsx files cannot: it replaces the
 * whole document, so it must render its own <html>/<body>.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased">
        <ErrorFallback error={error} reset={reset} scope="global" />
      </body>
    </html>
  );
}
