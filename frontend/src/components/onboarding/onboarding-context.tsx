"use client";

import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { stepIndexOf } from "@/lib/onboarding-steps";
import { getState } from "@/lib/api";
import type { OnboardingData } from "@/lib/types";

const DEFAULT_DATA: OnboardingData = {
  profile: { name: "", age: 0, weight_kg: 0, height_cm: 0 },
  experience: { climbing_years: 0, structured_training_years: 0 },
  grades: { lead_max_rp: "", lead_max_os: "" },
  goal: { goal_type: "lead_grade", discipline: "lead", target_grade: "", target_style: "redpoint", current_grade: "", deadline: "", total_weeks: 12 },
  self_eval: { primary_weakness: "", secondary_weakness: "" },
  tests: {},
  limitations: [],
  equipment: { home_enabled: true, home: [], gyms: [] },
  availability: {},
  planning_prefs: { target_training_days_per_week: 4, hard_day_cap_per_week: 3 },
  preferences: { finger_training_device: "hangboard" },
  trips: [],
  outdoor_spots: [],
};

/**
 * A245 Phase D (F16) — the draft used to live in `sessionStorage`, which dies
 * when the tab closes. On mobile that is the norm, not the exception: anyone
 * who stepped away around step 8-10 (~10 minutes of typing) came back to an
 * empty wizard. Highest-probability abandonment point in the funnel.
 *
 * Now: localStorage, scoped per user (same reasoning as A245 B-2 — an
 * unscoped draft would surface one user's answers to the next), with the
 * deepest step reached so we can offer to resume.
 */
const DRAFT_KEY_BASE = "climb_onboarding_draft";
/** Pre-A245 key. Tab-scoped, so reading it can never leak across users. */
const LEGACY_SESSION_KEY = "climb_onboarding_draft";
const DRAFT_TTL_MS = 30 * 24 * 60 * 60 * 1000;

type DraftEnvelope = {
  data: OnboardingData;
  deepestStep: number;
  savedAt: number;
};

function draftKey(): string {
  const userId =
    typeof window !== "undefined" ? window.Clerk?.user?.id : undefined;
  return `${DRAFT_KEY_BASE}_${userId ?? "anon"}`;
}

function loadDraft(): DraftEnvelope | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(draftKey());
    if (raw) {
      const env = JSON.parse(raw) as DraftEnvelope;
      if (env?.data && Date.now() - (env.savedAt ?? 0) < DRAFT_TTL_MS) return env;
      localStorage.removeItem(draftKey());
      return null;
    }
    // One-time bridge: a wizard already in flight in this tab when the new
    // build landed. sessionStorage is tab-scoped, so this is safe.
    const legacy = sessionStorage.getItem(LEGACY_SESSION_KEY);
    if (legacy) {
      return { data: JSON.parse(legacy) as OnboardingData, deepestStep: 0, savedAt: Date.now() };
    }
    return null;
  } catch {
    return null;
  }
}

function saveDraft(data: OnboardingData, deepestStep: number) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      draftKey(),
      JSON.stringify({ data, deepestStep, savedAt: Date.now() } satisfies DraftEnvelope),
    );
  } catch (err) {
    console.warn("[onboarding] could not save draft:", err);
  }
}

/** Called on successful submit, and by SessionScopeGuard when the user changes. */
export function clearOnboardingDraft(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(draftKey());
    sessionStorage.removeItem(LEGACY_SESSION_KEY);
  } catch {
    // Nothing to clear.
  }
}

/** Purge every onboarding draft on this device, whoever it belongs to. */
export function purgeAllOnboardingDrafts(): void {
  if (typeof window === "undefined") return;
  try {
    const doomed: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(DRAFT_KEY_BASE)) doomed.push(k);
    }
    doomed.forEach((k) => localStorage.removeItem(k));
    sessionStorage.removeItem(LEGACY_SESSION_KEY);
  } catch {
    // Nothing to purge.
  }
}

interface OnboardingContextType {
  data: OnboardingData;
  update: <K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => void;
  loaded: boolean;
  /** Furthest step index reached, for the resume affordance (F16). */
  deepestStep: number;
  clearDraft: () => void;
}

const OnboardingCtx = createContext<OnboardingContextType>({
  data: DEFAULT_DATA,
  update: () => {},
  loaded: false,
  deepestStep: 0,
  clearDraft: () => {},
});

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<OnboardingData>(DEFAULT_DATA);
  const [loaded, setLoaded] = useState(false);
  const [deepestStep, setDeepestStep] = useState(0);
  const pathname = usePathname();

  // A245 Phase D (F16) — track how far the user got, without touching a single
  // step page: the provider wraps them all and the route already says where we
  // are. Monotonic, so going Back doesn't lower the resume point.
  const deepestRef = useRef(0);
  useEffect(() => {
    const idx = stepIndexOf(pathname);
    if (idx > deepestRef.current) {
      deepestRef.current = idx;
      setDeepestStep(idx);
    }
  }, [pathname]);

  // Pre-populate: local draft first, then backend state as fallback
  useEffect(() => {
    const draft = loadDraft();
    // A245 Phase D (F16) — the old guard was `draft.profile.name`, so a draft
    // from anyone who hadn't reached (or filled) the name field was silently
    // discarded. Any stored draft is now honoured.
    if (draft) {
      setData(draft.data);
      deepestRef.current = draft.deepestStep;
      setDeepestStep(draft.deepestStep);
      setLoaded(true);
      return;
    }

    getState()
      .then((state) => {
        const d = { ...DEFAULT_DATA };
        const u = state.user as Record<string, unknown> | undefined;
        if (u?.name) {
          d.profile = {
            name: String(u.name || ""),
            preferred_name: u.preferred_name ? String(u.preferred_name) : undefined,
            age: Number(u.age || (state.body as Record<string, unknown>)?.age || 0),
            weight_kg: Number((state.body as Record<string, unknown>)?.weight_kg || 0),
            height_cm: Number((state.body as Record<string, unknown>)?.height_cm || 0),
            // D64: body_fat_pct removed — RED-S guardrail
          };
        }
        if (state.assessment?.experience) {
          d.experience = state.assessment.experience as OnboardingData["experience"];
        }
        if (state.assessment?.grades) {
          d.grades = state.assessment.grades as OnboardingData["grades"];
        }
        if (state.goal && Object.keys(state.goal).length > 0) {
          d.goal = state.goal as OnboardingData["goal"];
        }
        if (state.assessment?.self_eval) {
          d.self_eval = state.assessment.self_eval as OnboardingData["self_eval"];
        }
        if (state.assessment?.tests) {
          d.tests = state.assessment.tests as OnboardingData["tests"];
        }
        if (state.equipment && Object.keys(state.equipment).length > 0) {
          const eq = state.equipment as Record<string, unknown>;
          d.equipment = {
            // B272: respect the stored flag — hardcoding true silently
            // re-enabled home training for users who had disabled it.
            home_enabled:
              eq.home_enabled !== undefined
                ? Boolean(eq.home_enabled)
                : ((eq.home as string[]) || []).length > 0,
            home: (eq.home as string[]) || [],
            gyms: (eq.gyms as Array<{ name: string; equipment: string[] }>) || [],
          };
        }
        if (state.availability && Object.keys(state.availability).length > 0) {
          d.availability = state.availability as OnboardingData["availability"];
        }
        if (state.planning_prefs && Object.keys(state.planning_prefs).length > 0) {
          d.planning_prefs = state.planning_prefs as OnboardingData["planning_prefs"];
        }
        const prefs = (state as Record<string, unknown>).preferences as Record<string, unknown> | undefined;
        if (prefs?.finger_training_device) {
          d.preferences = { finger_training_device: prefs.finger_training_device as "hangboard" | "loading_pin" };
        }
        if (state.trips?.length) {
          d.trips = state.trips as OnboardingData["trips"];
        }
        const spots = (state as Record<string, unknown>).outdoor_spots;
        if (Array.isArray(spots) && spots.length > 0) {
          d.outdoor_spots = spots.map((s: Record<string, unknown>) => ({
            name: String(s.name || ""),
            discipline: (s.discipline as "lead" | "boulder" | "both") || "both",
          }));
        }
        const lim = state.limitations as Record<string, unknown> | undefined;
        if (lim?.details && Array.isArray(lim.details) && lim.details.length > 0) {
          d.limitations = lim.details as OnboardingData["limitations"];
        }
        setData(d);
        saveDraft(d, deepestRef.current);
      })
      .catch((err) => { console.error("Failed to load draft state from API:", err); })
      .finally(() => setLoaded(true));
  }, []);

  const update = useCallback(<K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => {
    setData((prev) => {
      const next = { ...prev, [key]: value };
      saveDraft(next, deepestRef.current);
      return next;
    });
  }, []);

  const clearDraft = useCallback(() => clearOnboardingDraft(), []);

  // A245 Phase D (F49) — this object literal used to be built inline, so every
  // keystroke handed a new `value` to the provider and re-rendered EVERY
  // consumer of the context, not just the field being typed into.
  const value = useMemo(
    () => ({ data, update, loaded, deepestStep, clearDraft }),
    [data, update, loaded, deepestStep, clearDraft],
  );

  return <OnboardingCtx.Provider value={value}>{children}</OnboardingCtx.Provider>;
}

export function useOnboarding() {
  return useContext(OnboardingCtx);
}
