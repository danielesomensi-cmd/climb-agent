"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { getState } from "@/lib/api";
import type { OnboardingData } from "@/lib/types";

const DEFAULT_DATA: OnboardingData = {
  profile: { name: "", age: 0, weight_kg: 0, height_cm: 0 },
  experience: { climbing_years: 0, structured_training_years: 0 },
  grades: { lead_max_rp: "", lead_max_os: "" },
  goal: { goal_type: "lead_grade", discipline: "lead", target_grade: "", target_style: "redpoint", current_grade: "", deadline: "" },
  self_eval: { primary_weakness: "", secondary_weakness: "" },
  tests: {},
  limitations: [],
  equipment: { home_enabled: true, home: [], gyms: [] },
  availability: {},
  planning_prefs: { target_training_days_per_week: 4, hard_day_cap_per_week: 3 },
  trips: [],
};

interface OnboardingContextType {
  data: OnboardingData;
  update: <K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => void;
  loaded: boolean;
}

const OnboardingCtx = createContext<OnboardingContextType>({
  data: DEFAULT_DATA,
  update: () => {},
  loaded: false,
});

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<OnboardingData>(DEFAULT_DATA);
  const [loaded, setLoaded] = useState(false);

  // Pre-populate from existing state
  useEffect(() => {
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
            body_fat_pct: (state.body as Record<string, unknown>)?.body_fat_pct ? Number((state.body as Record<string, unknown>).body_fat_pct) : undefined,
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
            home_enabled: true,
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
        if (state.trips?.length) {
          d.trips = state.trips as OnboardingData["trips"];
        }
        const lim = state.limitations as Record<string, unknown> | undefined;
        if (lim?.details && Array.isArray(lim.details) && lim.details.length > 0) {
          d.limitations = lim.details as OnboardingData["limitations"];
        }
        setData(d);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const update = useCallback(<K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => {
    setData((prev) => ({ ...prev, [key]: value }));
  }, []);

  return (
    <OnboardingCtx.Provider value={{ data, update, loaded }}>
      {children}
    </OnboardingCtx.Provider>
  );
}

export function useOnboarding() {
  return useContext(OnboardingCtx);
}
