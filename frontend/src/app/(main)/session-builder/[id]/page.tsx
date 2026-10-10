"use client";

import { Suspense, useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { SessionBuilder } from "@/components/session-builder/session-builder";
import { DiscardChangesDialog } from "@/components/session-builder/discard-changes-dialog";
import { BuilderSkeleton } from "@/components/session-builder/builder-skeleton";

const BACK_HREF = "/free-session";

export default function SessionBuilderEditPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  // B356 — il chevron della TopBar navigava via senza chiedere nulla: si
  // perdevano le modifiche in silenzio.
  const [dirty, setDirty] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleBack = useCallback(() => {
    if (dirty) setConfirmOpen(true);
    else router.push(BACK_HREF);
  }, [dirty, router]);

  return (
    <>
      <TopBar title="Session Builder" subtitle="Edit" onBack={handleBack} />
      <main className="px-4 py-4">
        <Suspense fallback={<BuilderSkeleton />}>
          <SessionBuilder sessionId={id} onDirtyChange={setDirty} />
        </Suspense>
      </main>
      <DiscardChangesDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={() => router.push(BACK_HREF)}
      />
    </>
  );
}
