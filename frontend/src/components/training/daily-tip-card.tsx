"use client";

import { useState } from "react";
import Link from "next/link";
import { Sparkles, X } from "lucide-react";
import { useDailyTip } from "@/lib/hooks/queries";
import { dismissDailyTip } from "@/lib/api";

interface DailyTipCardProps {
  /** Client-local date (YYYY-MM-DD) — seeds the deterministic daily pick. */
  date: string;
}

/**
 * A234: discreet feature-discovery card shown on /today below the daily
 * quote. One tip per day, deterministic per user (see backend tips_engine).
 * Dismiss hides it for the rest of the day (persisted server-side, so it
 * stays hidden across devices/reloads). Renders nothing while loading,
 * after dismissal, or if the tips endpoint is unavailable.
 */
export function DailyTipCard({ date }: DailyTipCardProps) {
  const { data } = useDailyTip(date);
  const [hidden, setHidden] = useState(false);

  const tip = data?.tip;
  if (!tip || hidden || data?.dismissed_today) return null;

  const handleDismiss = () => {
    setHidden(true); // optimistic — the card never blocks on the network
    dismissDailyTip(tip.id, date).catch(() => {});
  };

  return (
    <section
      aria-label="Tip of the day"
      className="relative mt-6 rounded-xl border border-sky-800/40 bg-gradient-to-r from-sky-950/40 to-sky-900/20 p-4"
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss tip"
        className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
      <div className="flex items-start gap-3 pr-8">
        <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-sky-400" aria-hidden="true" />
        <div className="min-w-0">
          <p className="mb-1 text-xs font-medium text-sky-400">Did you know?</p>
          <p className="text-sm leading-relaxed text-zinc-200">{tip.text}</p>
          {tip.cta_url && tip.cta_label && (
            <Link
              href={tip.cta_url}
              className="mt-2 inline-block text-sm font-medium text-sky-400 underline-offset-4 hover:underline"
            >
              {tip.cta_label} →
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
