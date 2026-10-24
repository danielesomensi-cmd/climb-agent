// A187 — Barrel export for query hooks.
export { useUserState, useStateStatus } from "./use-user-state";
export { useWeekPlan } from "./use-week-plan";
export {
  useOutdoorSpots,
  useOutdoorSessions,
  useOutdoorStats,
  useOutdoorLog,
  useQuaderno,
} from "./use-outdoor";
export { useOutdoorDoneDays } from "./use-outdoor-sessions";
export type { OutdoorDaysSummary } from "./use-outdoor-sessions";
export {
  useFreeSessionSurfaces,
  useFreeSessionPresets,
  useFreeSessionsForDates,
} from "./use-free-session";
export { useCatalogSessions, useCatalogExercises } from "./use-catalog";
export {
  useDailyQuote,
  useDailyTip,
  useMilestones,
  useMonthlyHeatmap,
  useOnboardingDefaults,
  useWeeklyReport,
  useReplannerSuggestions,
} from "./use-misc";
export {
  useCustomSessions,
  useCustomSession,
  useBuilderExercises,
  useBuilderBlocks,
} from "./use-custom-sessions";
