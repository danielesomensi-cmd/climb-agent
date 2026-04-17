"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { SessionBuilder } from "@/components/session-builder/session-builder";

export default function SessionBuilderEditPage() {
  const params = useParams();
  const id = params.id as string;

  return (
    <>
      <TopBar title="Session Builder" subtitle="Edit" backHref="/free-session" />
      <main className="px-4 py-4">
        <Suspense fallback={<p className="text-sm text-muted-foreground text-center py-8">Loading...</p>}>
          <SessionBuilder sessionId={id} />
        </Suspense>
      </main>
    </>
  );
}
