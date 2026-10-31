// C280: catalog exercises that share a movement with a core-circuit exercise
// reuse its illustration in the guided and custom players. Frontend-only on
// purpose: the catalog has no image field, and a map here reaches every launch
// path (planned, custom, coach, Body Part Picker) without touching the API.
//
// Only exact matches: same position, not just same muscles. Near variants
// (weighted hollow, bent-knee raises, v_sit with hands behind) stay without
// an image rather than show a different exercise. Side-specific moves show the
// right-side picture unless the caller knows it is the left side's turn.

const CORE_DIR = "/exercises/core/";

export const CATALOG_EXERCISE_IMAGES: Readonly<Record<string, string>> = {
  core_hollow_hold: "01_hollow_body.webp",
  dead_bug: "02_dead_bug.webp",
  plank_shoulder_tap: "03_plank_shoulder_taps.webp",
  kneeling_superman: "06_bird_dog.webp",
  side_plank: "10_side_plank_r.webp",
  copenhagen_plank: "12_copenhagen_r.webp",
  copenhagen_adductor_plank: "12_copenhagen_r.webp",
  v_up: "14_v_up.webp",
  glute_bridge: "20_glute_bridge.webp",
  lying_windshield_wiper: "25_windshield_wipers.webp",
  core_l_sit: "26_l_sit_floor.webp",
  test_l_sit_hold: "26_l_sit_floor.webp",
  single_leg_glute_bridge: "30_sl_glute_bridge.webp",
  dragon_flag_tuck: "31_dragon_flag_tuck.webp",
  front_lever_tuck: "32_front_lever_tuck.webp",
  windshield_wipers: "33_hanging_wipers.webp",
  side_plank_star: "34_star_side_plank_r.webp",
  straddle_l_sit: "36_straddle_l_sit.webp",
  hanging_leg_raise_horizontal: "38_hanging_leg_raise.webp",
  nordic_curl: "39_nordic_curl.webp",
  arch_hold: "40_arch_body_hold.webp",
};

const LEFT_SIDE: Readonly<Record<string, string>> = {
  "10_side_plank_r.webp": "11_side_plank_l.webp",
  "12_copenhagen_r.webp": "13_copenhagen_l.webp",
  "34_star_side_plank_r.webp": "35_star_side_plank_l.webp",
};

/** Public path of the illustration for a catalog exercise, or null. */
export function exerciseImage(
  exerciseId: string | null | undefined,
  side?: "RIGHT" | "LEFT" | null,
): string | null {
  const file = exerciseId ? CATALOG_EXERCISE_IMAGES[exerciseId] : undefined;
  if (!file) return null;
  return CORE_DIR + (side === "LEFT" ? (LEFT_SIDE[file] ?? file) : file);
}
