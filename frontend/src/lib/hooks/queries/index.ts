// A187 — Barrel export for query hooks.
export { useUserState, useStateStatus } from "./use-user-state";
export { useWeekPlan } from "./use-week-plan";
export {
  useOutdoorSpots,
  useOutdoorSessions,
  useOutdoorStats,
  useOutdoorLog,
} from "./use-outdoor";
export {
  useFreeSessionSurfaces,
  useFreeSessionPresets,
  useFreeSessionHistory,
} from "./use-free-session";
export { useCatalogSessions, useCatalogExercises } from "./use-catalog";
export {
  useDailyQuote,
  useDailyTip,
  useMonthlyHeatmap,
  useOnboardingDefaults,
  useSubscriptionStatus,
  useWeeklyReport,
  useReplannerSuggestions,
} from "./use-misc";
export {
  useCustomSessions,
  useCustomSession,
  useBuilderExercises,
  useBuilderBlocks,
} from "./use-custom-sessions";
