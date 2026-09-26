"use client";

import {
  OnboardingProvider,
  useOnboarding,
} from "@/components/onboarding/onboarding-context";
import { StepIndicator } from "@/components/onboarding/step-indicator";
import { ReturnToReviewBar } from "@/components/onboarding/return-to-review-bar";
import { stepIndexOf } from "@/lib/onboarding-steps";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

/**
 * A286 (C11) — transizione d'ingresso dello step. 12 hard cut su contenuti di
 * altezza molto diversa. È CSS e non JS di proposito: il blocco globale
 * `prefers-reduced-motion` in globals.css azzera le animation-duration, quindi
 * chi ha chiesto meno movimento non ne vede nessuno senza codice in più.
 */
const STEP_TRANSITION_CSS = `
@keyframes a286-step-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: none; }
}
.a286-step-in { animation: a286-step-in 150ms ease-out both; }
`;

/** Oltre questo, mostriamo comunque il form: meglio i default che uno spinner eterno. */
const DRAFT_WAIT_TIMEOUT_MS = 5000;

/**
 * A286 (C4) — il wizard renderizzava i default PRIMA che la bozza fosse
 * risolta: al rientro il form appariva vuoto e quello che l'utente digitava in
 * quella finestra veniva sovrascritto senza alcun segnale dalla bozza che
 * arrivava dopo. Non renderizziamo i campi finché `loaded` non è vero — è la
 * soluzione più semplice e non tocca il formato della bozza.
 *
 * Solo per gli step del wizard: `welcome` (landing pubblica), `install` e
 * `start-week` non leggono la bozza e non devono mai aspettare Clerk.
 * E il gate ha comunque un timeout: se clerk-js è bloccato `loaded` può non
 * arrivare mai, e uno spinner infinito sarebbe peggio del bug che risolve.
 */
function StepFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loaded } = useOnboarding();
  const needsDraft = stepIndexOf(pathname) >= 0;
  const [waitedTooLong, setWaitedTooLong] = useState(false);

  useEffect(() => {
    if (loaded || !needsDraft) return;
    const t = setTimeout(() => setWaitedTooLong(true), DRAFT_WAIT_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [loaded, needsDraft]);

  if (needsDraft && !loaded && !waitedTooLong) {
    return (
      <main className="flex-1 px-4 pb-8">
        <div
          className="mx-auto flex max-w-lg items-center justify-center gap-3 pt-16 text-sm text-muted-foreground"
          role="status"
        >
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          Loading your answers...
        </div>
      </main>
    );
  }

  return (
    <main key={pathname} className="a286-step-in flex-1 px-4 pb-8">
      {children}
    </main>
  );
}

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OnboardingProvider>
      <style>{STEP_TRANSITION_CSS}</style>
      <div className="min-h-screen flex flex-col">
        {/* A245 Phase D (F47) — one-tap return when arriving from the summary */}
        <Suspense fallback={null}>
          <ReturnToReviewBar />
        </Suspense>
        <StepIndicator />
        <StepFrame>{children}</StepFrame>
      </div>
    </OnboardingProvider>
  );
}
