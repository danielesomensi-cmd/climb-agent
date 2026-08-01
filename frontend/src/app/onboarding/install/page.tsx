"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { InstallCard } from "@/components/install/install-card";

function InstallPageInner() {
  const router = useRouter();
  const params = useSearchParams();
  // Where to go once done. Whitelisted: this comes from a URL.
  const requested = params.get("next");
  const nextHref = requested === "/subscribe" ? "/subscribe" : "/today";

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Keep it one tap away</CardTitle>
          <CardDescription>
            Installed, climb-agent opens full-screen, starts from your home
            screen, and keeps today&apos;s session available without signal.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* A260: the steps used to be a static iPhone/Android tab pair with
              iPhone hardcoded as the default, so an Android user read Safari
              instructions until they noticed the tab. InstallCard reads what
              this browser can actually do — one-tap native prompt on Chromium,
              menu steps on iOS, "leave this webview" inside Instagram/Facebook
              — so nobody is handed instructions they cannot follow. */}
          <InstallCard onDone={() => router.push(nextHref)} />
        </CardContent>
      </Card>

      {/* A245 Phase D (F38) — this screen used to be step 2 of 14: the very
          first thing asked after sign-up, before the user had seen a single
          thing the app does. Asking for a home-screen install before any
          perceived value is the classic way to lose people at the top of the
          funnel. It now runs after the plan exists, so the ask lands when
          there is something worth coming back to. */}
    </div>
  );
}

export default function InstallPage() {
  return (
    <Suspense fallback={null}>
      <InstallPageInner />
    </Suspense>
  );
}
