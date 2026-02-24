"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Timer,
  Mountain,
  BarChart3,
  Video,
  Bot,
  Smartphone,
  ClipboardCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { FeatureItem } from "./feature-item";

interface Feature {
  slug: string;
  icon: LucideIcon;
  label: string;
  implemented?: boolean;
}

const SHORT_TERM: Feature[] = [
  { slug: "rest-timer", icon: Timer, label: "Rest timer — countdown between sets with beep", implemented: true },
  { slug: "outdoor-logging", icon: Mountain, label: "Outdoor session logging — log your crag sessions" },
  { slug: "progress-reports", icon: BarChart3, label: "Progress reports — weekly and monthly stats" },
];

const LONG_TERM: Feature[] = [
  { slug: "kilter-ai", icon: Video, label: "Kilter Board AI analysis — video feedback on your moves" },
  { slug: "ai-coach", icon: Bot, label: "AI coach — chat with your training coach" },
  { slug: "kilter-integration", icon: Smartphone, label: "Kilter App integration — sync your board sessions" },
  { slug: "testing-week", icon: ClipboardCheck, label: "Testing week — dedicated assessment week after onboarding" },
];

const STORAGE_KEY = "climb_whats_next_votes";

function loadVotes(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function saveVotes(votes: Record<string, boolean>) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(votes));
}

export function RoadmapSection() {
  const [votes, setVotes] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setVotes(loadVotes());
  }, []);

  const toggle = useCallback((slug: string) => {
    setVotes((prev) => {
      const next = { ...prev };
      if (next[slug]) {
        delete next[slug];
      } else {
        next[slug] = true;
      }
      saveVotes(next);
      return next;
    });
  }, []);

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Coming soon</h2>
        <p className="text-sm text-muted-foreground">Vote for what you want to see next</p>
      </div>

      <div className="space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Coming next
        </h3>
        <div className="space-y-2">
          {SHORT_TERM.map((f) => (
            <FeatureItem
              key={f.slug}
              icon={f.icon}
              label={f.label}
              voted={!!votes[f.slug]}
              onToggle={() => toggle(f.slug)}
              implemented={f.implemented}
            />
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Bigger features
        </h3>
        <div className="space-y-2">
          {LONG_TERM.map((f) => (
            <FeatureItem
              key={f.slug}
              icon={f.icon}
              label={f.label}
              voted={!!votes[f.slug]}
              onToggle={() => toggle(f.slug)}
            />
          ))}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Got an idea? Tell us below
      </p>
    </section>
  );
}
