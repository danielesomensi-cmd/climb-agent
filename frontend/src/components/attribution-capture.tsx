"use client";

import { useEffect } from "react";
import { captureUtmOnMount } from "@/lib/analytics";

/**
 * A233 — First-touch attribution capture, mounted once in the root layout so
 * every landing page (/, /demo, /onboarding/*, …) records UTM + referrer +
 * landing path on the visitor's first hit. Renders nothing.
 */
export function AttributionCapture() {
  useEffect(() => {
    captureUtmOnMount();
  }, []);
  return null;
}
