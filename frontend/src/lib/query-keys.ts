/**
 * A187 — Centralised React Query keys.
 *
 * Single source of truth for all cache keys. Hooks and mutations import
 * from here so invalidation always uses the same key shape. Prefix-based
 * invalidation (e.g. queryClient.invalidateQueries({ queryKey: ['week'] }))
 * relies on these arrays starting with a stable string.
 *
 * See docs/audit/D176_invalidation_map.md for the full mapping.
 */

export const queryKeys = {
  // State
  state: ["state"] as const,
  stateStatus: ["state", "status"] as const,

  // Week plan (parameterised by week number, 0 = current)
  week: (weekNum: number) => ["week", weekNum] as const,
  weekAll: ["week"] as const, // prefix for invalidating every week

  // Catalog (immutable)
  catalogSessions: ["catalog", "sessions"] as const,
  catalogExercises: ["catalog", "exercises"] as const,

  // Outdoor
  outdoorSpots: ["outdoor", "spots"] as const,
  outdoorSessions: (since?: string) => ["outdoor", "sessions", since ?? null] as const,
  outdoorSessionsAll: ["outdoor", "sessions"] as const,
  outdoorLog: (date: string) => ["outdoor", "log", date] as const,
  outdoorStats: (since?: string) => ["outdoor", "stats", since ?? null] as const,
  outdoorStatsAll: ["outdoor", "stats"] as const,
  outdoorAll: ["outdoor"] as const, // prefix

  // Free session
  freeSessionSurfaces: ["free-session", "surfaces"] as const,
  freeSessionPresets: (surface: string) => ["free-session", "presets", surface] as const,
  freeSessionHistory: (date: string) => ["free-session", "history", date] as const,
  freeSessionHistoryAll: ["free-session", "history"] as const,

  // Replanner
  replannerSuggest: (date: string, location: string) =>
    ["replanner", "suggest", date, location] as const,

  // Reports
  reportsWeekly: (weekStart: string) => ["reports", "weekly", weekStart] as const,

  // Quotes
  quotesDaily: (context: string) => ["quotes", "daily", context] as const,

  // Daily tips (A234)
  tipsDaily: (date: string) => ["tips", "daily", date] as const,

  // Onboarding defaults (static)
  onboardingDefaults: ["onboarding", "defaults"] as const,

  // Subscription
  subscriptionStatus: ["subscription", "status"] as const,

  // Weekly override
  weeklyOverride: (weekStart: string) => ["weekly-override", weekStart] as const,

  // Custom sessions (A206)
  customSessions: ["custom-session", "list"] as const,
  customSession: (id: string) => ["custom-session", "detail", id] as const,
  customSessionAll: ["custom-session"] as const, // prefix
  builderExercises: (q: string, domain: string) => ["custom-session", "exercises", q, domain] as const,
  builderBlocks: ["custom-session", "blocks"] as const,
} as const;
