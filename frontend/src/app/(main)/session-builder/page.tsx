"use client";

import { Suspense } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { SessionBuilder } from "@/components/session-builder/session-builder";

export default function SessionBuilderPage() {
  return (
    <>
      <TopBar title="Session Builder" backHref="/free-session" />
      <main className="px-4 py-4">
        <Suspense fallback={<p className="text-sm text-muted-foreground text-center py-8">Loading...</p>}>
          <SessionBuilder sessionId={null} />
        </Suspense>
      </main>
    </>
  );
}
