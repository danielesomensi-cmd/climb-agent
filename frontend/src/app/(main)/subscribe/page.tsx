"use client";

import { Suspense } from "react";
import { SubscribeContent } from "./SubscribeContent";

/**
 * `SubscribeContent` uses `useSearchParams()` for the ?preview=1 affordance.
 * Next.js 16 / Turbopack requires a Suspense boundary around client-side
 * bailouts even on dynamic routes — wrap the inner content here.
 */
export default function SubscribePage() {
  return (
    <Suspense fallback={null}>
      <SubscribeContent />
    </Suspense>
  );
}
