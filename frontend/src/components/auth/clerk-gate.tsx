"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";

/**
 * B339 — `/sign-in` and `/sign-up` render `<SignIn />` / `<SignUp />` and
 * nothing else. Those components draw **nothing at all** until Clerk's
 * frontend API (`clerk.climbagent.app`) answers, so when that host is
 * unreachable the page is a black rectangle: no spinner, no message, no way
 * for the visitor to tell whether the app is broken or their own network is.
 *
 * Reproduced 2026-08-19 against production with Playwright: block
 * `clerk.climbagent.app` and the sign-in page renders an empty body, exactly
 * the "I click sign in and nothing opens" report. Production itself was
 * healthy throughout — FAPI 200, DNS and certificate fine — which is the whole
 * problem: the failure is on the visitor's side and the UI said nothing, so
 * the app took the blame.
 *
 * Who actually hits this: corporate networks and VPNs that don't resolve an
 * unknown subdomain, and privacy extensions — `clerk` matches entries on some
 * tracker blocklists.
 *
 * Deliberately NOT a hard failure: `isLoaded` flipping true after the timeout
 * still wins, so a merely slow network resolves into the real form.
 */
const CLERK_LOAD_TIMEOUT_MS = 8000;

const FAPI_HOST =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith("pk_live")
    ? "clerk.climbagent.app"
    : null;

export function ClerkGate({ children }: { children: React.ReactNode }) {
  const { isLoaded } = useAuth();
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (isLoaded) return;
    const timer = setTimeout(() => setTimedOut(true), CLERK_LOAD_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [isLoaded]);

  if (isLoaded) return <>{children}</>;

  if (!timedOut) {
    return (
      <div
        className="flex min-h-screen items-center justify-center px-6"
        role="status"
        aria-live="polite"
      >
        <p className="text-sm text-muted-foreground">Loading sign-in…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <span className="text-4xl" aria-hidden="true">
        🔌
      </span>
      <h1 className="text-xl font-semibold">Can&apos;t reach the sign-in service</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Your account is fine and so is your training data — this device just
        can&apos;t reach the service that handles sign-in.
      </p>
      <ul className="max-w-sm space-y-1 text-left text-sm text-muted-foreground">
        <li>• A company network or VPN blocking an unknown domain</li>
        <li>• An ad-blocker or privacy extension</li>
        <li>• No internet connection right now</li>
      </ul>
      <div className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="flex min-h-[44px] items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground"
        >
          Try again
        </button>
        <a
          href="/onboarding/welcome"
          className="flex min-h-[44px] items-center justify-center rounded-md border px-6 text-sm font-medium"
        >
          Back
        </a>
      </div>
      {FAPI_HOST && (
        <p className="max-w-sm pt-2 text-xs text-muted-foreground/70">
          To confirm, open{" "}
          <a
            className="underline underline-offset-2"
            href={`https://${FAPI_HOST}/v1/environment`}
          >
            {FAPI_HOST}
          </a>{" "}
          in this browser. If that fails too, the block is on this network — try
          mobile data or another browser.
        </p>
      )}
    </div>
  );
}
