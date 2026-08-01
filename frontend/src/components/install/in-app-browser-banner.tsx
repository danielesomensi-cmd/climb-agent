"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, ExternalLink } from "lucide-react";
import { useInstall } from "@/lib/hooks/use-install";
import { trackEvent } from "@/lib/analytics";

/**
 * A261 — the warning that belongs on the *landing* pages, not in the wizard.
 *
 * A260 taught the install screen to recognise social webviews, but that screen
 * sits behind auth at the end of onboarding. Someone arriving from an Instagram
 * or Reddit link lands here instead, inside the host app's embedded browser —
 * and hits two walls before ever reaching it:
 *
 *   1. A PWA cannot be installed from a webview at all.
 *   2. Google refuses OAuth inside embedded webviews (`disallowed_useragent`),
 *      so "Sign up with Google" can fail outright — at the exact moment we are
 *      asking a cold visitor for an account.
 *
 * Both are invisible failures: the user sees a dead button and leaves, and we
 * record it as a bounce. Since this is the surface paid and social traffic will
 * land on, saying it out loud costs one banner and saves the visit.
 *
 * Renders nothing in a normal browser, so it is safe to mount unconditionally.
 */
export function InAppBrowserBanner() {
  const { capability } = useInstall();
  const [copied, setCopied] = useState(false);
  const tracked = useRef(false);

  useEffect(() => {
    if (capability !== "in-app-browser" || tracked.current) return;
    tracked.current = true;
    // Counted separately from the install funnel: this is an *acquisition*
    // measurement — how much of the incoming traffic lands somewhere it cannot
    // convert. Without it, those visits are indistinguishable from bounces.
    trackEvent("landing_in_app_browser");
  }, [capability]);

  if (capability !== "in-app-browser") return null;

  return (
    <div className="mx-auto mb-4 max-w-lg rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <ExternalLink className="h-4 w-4 shrink-0" />
        Open this page in your browser
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        You&apos;re viewing this inside another app. Signing up with Google
        doesn&apos;t work here, and the app can&apos;t be installed. Copy the
        link and open it in Safari or Chrome.
      </p>
      <button
        onClick={async () => {
          const url = window.location.href;
          try {
            await navigator.clipboard.writeText(url);
            setCopied(true);
            toast.success("Link copied — paste it in Safari or Chrome");
            trackEvent("landing_copy_link");
          } catch {
            // Clipboard access is denied in some webviews; showing the address
            // is the only remaining path, so it must not fail silently.
            toast.error(`Copy this address: ${url}`);
          }
        }}
        className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-semibold text-background"
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        {copied ? "Link copied" : "Copy link"}
      </button>
    </div>
  );
}
