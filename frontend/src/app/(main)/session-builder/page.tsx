"use client";

import { Suspense, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { SessionBuilder } from "@/components/session-builder/session-builder";
import { DiscardChangesDialog } from "@/components/session-builder/discard-changes-dialog";
import { BuilderSkeleton } from "@/components/session-builder/builder-skeleton";

const BACK_HREF = "/free-session";

export default function SessionBuilderPage() {
  const router = useRouter();
  // B356 — vedi la pagina di modifica: il back usciva senza chiedere conferma,
  // e qui si perde una sessione composta da zero.
  const [dirty, setDirty] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleBack = useCallback(() => {
    if (dirty) setConfirmOpen(true);
    else router.push(BACK_HREF);
  }, [dirty, router]);

  return (
    <>
      <TopBar title="Session Builder" onBack={handleBack} />
      <main className="px-4 py-4">
        <Suspense fallback={<BuilderSkeleton />}>
          <SessionBuilder sessionId={null} onDirtyChange={setDirty} />
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
