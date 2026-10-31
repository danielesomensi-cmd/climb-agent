// C280: catalog exercises that share a movement with a core-circuit exercise
// reuse its illustration in the guided and custom players. Frontend-only on
// purpose: the catalog has no image field, and a map here reaches every launch
// path (planned, custom, coach, Body Part Picker) without touching the API.
// C281: cooldown and flexibility exercises reuse the Mobility stretch
// illustrations the same way (the Mobility flow itself reads `image` from the
// mobility catalog).
//
// Only exact matches: same position, not just same muscles. Near variants
// (weighted hollow, bent-knee raises, v_sit with hands behind) stay without
// an image rather than show a different exercise. Side-specific moves show the
// right-side picture unless the caller knows it is the left side's turn.

const DIR = "/exercises/";

export const CATALOG_EXERCISE_IMAGES: Readonly<Record<string, string>> = {
  core_hollow_hold: "core/01_hollow_body.webp",
  dead_bug: "core/02_dead_bug.webp",
  plank_shoulder_tap: "core/03_plank_shoulder_taps.webp",
  kneeling_superman: "core/06_bird_dog.webp",
  side_plank: "core/10_side_plank_r.webp",
  copenhagen_plank: "core/12_copenhagen_r.webp",
  copenhagen_adductor_plank: "core/12_copenhagen_r.webp",
  v_up: "core/14_v_up.webp",
  glute_bridge: "core/20_glute_bridge.webp",
  lying_windshield_wiper: "core/25_windshield_wipers.webp",
  core_l_sit: "core/26_l_sit_floor.webp",
  test_l_sit_hold: "core/26_l_sit_floor.webp",
  single_leg_glute_bridge: "core/30_sl_glute_bridge.webp",
  dragon_flag_tuck: "core/31_dragon_flag_tuck.webp",
  front_lever_tuck: "core/32_front_lever_tuck.webp",
  windshield_wipers: "core/33_hanging_wipers.webp",
  side_plank_star: "core/34_star_side_plank_r.webp",
  straddle_l_sit: "core/36_straddle_l_sit.webp",
  hanging_leg_raise_horizontal: "core/38_hanging_leg_raise.webp",
  nordic_curl: "core/39_nordic_curl.webp",
  arch_hold: "core/40_arch_body_hold.webp",
  // C281 — stretches
  cooldown_forearm_wrist_stretch: "stretch/stretch_finger_flexor.webp",
  forearm_stretches: "stretch/stretch_finger_flexor.webp",
  cooldown_hamstring_fold: "stretch/stretch_standing_forward_fold.webp",
  cooldown_hip_pigeon: "stretch/stretch_pigeon.webp",
  cooldown_spinal_twist: "stretch/stretch_supine_twist.webp",
  cooldown_deep_squat_hold: "stretch/stretch_deep_squat.webp",
  cooldown_shoulder_chest: "stretch/stretch_doorway_chest.webp",
  lat_overhead_stretch: "stretch/stretch_lat_triceps.webp",
  hip_flexor_couch_stretch: "stretch/hip_flexor_couch_stretch.webp",
  cooldown_hip_frog: "stretch/cooldown_hip_frog.webp",
};

const LEFT_SIDE: Readonly<Record<string, string>> = {
  "core/10_side_plank_r.webp": "core/11_side_plank_l.webp",
  "core/12_copenhagen_r.webp": "core/13_copenhagen_l.webp",
  "core/34_star_side_plank_r.webp": "core/35_star_side_plank_l.webp",
};

/** C281: a one-sided stretch ships its mirrored picture as `<name>_l.webp`. */
function leftStretch(path: string): string {
  return path.replace(/\.webp$/, "_l.webp");
}

/** Public path of the illustration for a catalog exercise, or null. */
export function exerciseImage(
  exerciseId: string | null | undefined,
  side?: "RIGHT" | "LEFT" | null,
): string | null {
  const file = exerciseId ? CATALOG_EXERCISE_IMAGES[exerciseId] : undefined;
  if (!file) return null;
  if (side !== "LEFT") return DIR + file;
  return DIR + (LEFT_SIDE[file] ?? (file.startsWith("stretch/") ? leftStretch(file) : file));
}

/**
 * C281: picture for a Mobility flow step — the catalog's `image`, mirrored on
 * the left side's turn (the flow sets `side` only on one-sided stretches).
 */
export function mobilityStepImage(
  image: string | null | undefined,
  side: "left" | "right" | null,
): string | null {
  if (!image) return null;
  return side === "left" ? leftStretch(image) : image;
}
