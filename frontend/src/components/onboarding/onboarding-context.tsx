"use client";

import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { stepIndexOf } from "@/lib/onboarding-steps";
import { getState, getOnboardingDraft, putOnboardingDraft } from "@/lib/api";
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

/**
 * B293 — the key is derived from the CALLER-supplied Clerk user id, never read
 * from `window.Clerk` inside this module's load path. `window.Clerk` is set by
 * clerk-js loading asynchronously: the provider's mount effect used to race it,
 * read the `_anon` key on every reload, miss the real `_user_XXX` draft, fall
 * back to a near-empty `getState()` and then SAVE those defaults over the good
 * draft once Clerk finished loading. That was the mid-wizard data loss.
 */
export function draftKey(userId?: string | null): string {
  const uid =
    userId !== undefined
      ? userId
      : typeof window !== "undefined"
        ? window.Clerk?.user?.id
        : undefined;
  return `${DRAFT_KEY_BASE}_${uid ?? "anon"}`;
}

function readDraftAt(key: string): DraftEnvelope | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const env = JSON.parse(raw) as DraftEnvelope;
    if (env?.data && Date.now() - (env.savedAt ?? 0) < DRAFT_TTL_MS) return env;
    localStorage.removeItem(key);
    return null;
  } catch {
    return null;
  }
}

function loadDraft(userId: string | null): DraftEnvelope | null {
  if (typeof window === "undefined") return null;
  try {
    const own = readDraftAt(draftKey(userId));
    if (own) return own;
    // A draft started while anonymous (pre-signup on this device) belongs to
    // whoever just signed in here — adopt it instead of losing it.
    if (userId) {
      const anon = readDraftAt(draftKey(null));
      if (anon) return anon;
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

function saveDraft(data: OnboardingData, deepestStep: number, userId: string | null) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      draftKey(userId),
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
    // A256 — the anonymous draft must go too. It only ever gets adopted (see
    // loadDraft) and never cleared, so before this brief it survived submit as
    // an orphan under `_anon`. Harmless while the wizard was auth-walled and
    // nobody could produce one; a leak the moment the wizard went public — the
    // next visitor on a shared phone (gym tablet, a friend's device) starts the
    // wizard anonymously and gets the previous person's answers pre-filled.
    localStorage.removeItem(draftKey(null));
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
  // B293 — the load path must know WHO the user is before touching storage or
  // the API, so everything waits for Clerk instead of racing it.
  const { isLoaded: authLoaded, userId: clerkUserId } = useAuth();
  const userIdRef = useRef<string | null>(null);
  userIdRef.current = clerkUserId ?? null;

  // A245 Phase D (F16) — track how far the user got, without touching a single
  // step page: the provider wraps them all and the route already says where we
  // are. Monotonic, so going Back doesn't lower the resume point.
  const deepestRef = useRef(0);

  // B293 — server-side draft push. Debounced while typing (update below),
  // flushed on step navigation: reaching the next step is the natural
  // "this step is complete" moment. Fire-and-forget: a failed push never
  // blocks the wizard, the local draft remains the safety net.
  const dataRef = useRef(data);
  dataRef.current = data;
  const loadedRef = useRef(false);
  loadedRef.current = loaded;
  const pushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pushServerDraft = useCallback(() => {
    if (!userIdRef.current || !loadedRef.current) return;
    putOnboardingDraft({
      data: dataRef.current,
      deepest_step: deepestRef.current,
      saved_at: Date.now(),
    }).catch(() => {});
  }, []);
  useEffect(
    () => () => {
      if (pushTimerRef.current) clearTimeout(pushTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    const idx = stepIndexOf(pathname);
    if (idx > deepestRef.current) {
      deepestRef.current = idx;
      setDeepestStep(idx);
    }
    // B293: flush the pending draft to the server on every step change.
    if (pushTimerRef.current) {
      clearTimeout(pushTimerRef.current);
      pushTimerRef.current = null;
    }
    pushServerDraft();
  }, [pathname, pushServerDraft]);

  // Pre-populate: local draft first, then backend state as fallback.
  //
  // B293 — gated on Clerk being loaded, and split by auth state:
  //  - anonymous visitor (public /onboarding/welcome): NEVER call getState().
  //    Since B285 an anonymous request gets an authoritative 401, and the 401
  //    handler in api.ts hard-redirects to /sign-in — which is exactly the
  //    regression that made the public welcome page unreadable.
  //  - signed-in user: draft is looked up under the REAL user key (no more
  //    `_anon` misses on reload), with getState() as the last fallback.
  const startedRef = useRef(false);
  useEffect(() => {
    if (!authLoaded || startedRef.current) return;
    startedRef.current = true;
    const uid = clerkUserId ?? null;

    // A245 Phase D (F16) — the old guard was `draft.profile.name`, so a draft
    // from anyone who hadn't reached (or filled) the name field was silently
    // discarded. Any stored draft is now honoured.
    const local = loadDraft(uid);

    const applyEnvelope = (env: DraftEnvelope) => {
      // Shallow-merge over defaults so a draft written by an older build
      // (missing a later-added section) can never render undefined sections.
      setData({ ...DEFAULT_DATA, ...env.data });
      deepestRef.current = env.deepestStep;
      setDeepestStep(env.deepestStep);
      // Mirror under the user's own key (adopts pre-signup anonymous drafts
      // and keeps the local copy in sync with a server-won reconcile).
      if (uid) saveDraft(env.data, env.deepestStep, uid);
    };

    if (!uid) {
      // Anonymous: local draft or defaults — and no API call to make.
      if (local) applyEnvelope(local);
      setLoaded(true);
      return;
    }

    const prefillFromState = () => getState()
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
        saveDraft(d, deepestRef.current, uid);
      })
      .catch((err) => { console.error("Failed to load draft state from API:", err); })
      .finally(() => setLoaded(true));

    // B293 — signed in: reconcile the server-side draft with the local one.
    // Newer `savedAt` wins: a re-auth (or another device) must restore what
    // the server has, but fresher local edits that never reached the server
    // must not be rolled back either.
    getOnboardingDraft()
      .then(({ draft: server }) => {
        const serverEnv: DraftEnvelope | null = server?.data
          ? {
              data: server.data,
              deepestStep: server.deepest_step ?? 0,
              savedAt: server.saved_at ?? 0,
            }
          : null;
        const chosen =
          serverEnv && local
            ? (serverEnv.savedAt ?? 0) > (local.savedAt ?? 0)
              ? serverEnv
              : local
            : serverEnv ?? local;
        if (chosen) {
          applyEnvelope(chosen);
          setLoaded(true);
          return;
        }
        void prefillFromState();
      })
      .catch(() => {
        // Draft endpoint unreachable — the local draft still lets the wizard go on.
        if (local) {
          applyEnvelope(local);
          setLoaded(true);
          return;
        }
        void prefillFromState();
      });
  }, [authLoaded, clerkUserId]);

  const update = useCallback(<K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => {
    setData((prev) => {
      const next = { ...prev, [key]: value };
      saveDraft(next, deepestRef.current, userIdRef.current);
      return next;
    });
    // B293: debounced server push (2s after the last edit).
    if (userIdRef.current) {
      if (pushTimerRef.current) clearTimeout(pushTimerRef.current);
      pushTimerRef.current = setTimeout(pushServerDraft, 2000);
    }
  }, [pushServerDraft]);

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
