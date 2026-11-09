// C280: catalog exercises that share a movement with a core-circuit exercise
// reuse its illustration in the guided and custom players. Frontend-only on
// purpose: the catalog has no image field, and a map here reaches every launch
// path (planned, custom, coach, Body Part Picker) without touching the API.
// C281: cooldown and flexibility exercises reuse the Mobility stretch
// illustrations the same way (the Mobility flow itself reads `image` from the
// mobility catalog).
// C282: the strength and prehab moves Daniele's plans use most whose name does
// not show the position (front lever one leg, wall slide, face pull, wrist
// curls…) get their own illustration in `strength/`. Knees to elbows and the
// thigh-supported elbow eccentric curl stay without one (no exact picture).
// C285: technique drills whose position a name cannot teach (backstep, drop
// knee, flag…) get their own illustration in `technique/`, made from a 3D
// mannequin pose and checked by an adversarial coach review (recipe in
// scripts/illustrations/README.md). Drills that are rules, tempos or attempt
// protocols stay without a picture on purpose. A drill whose lesson needs a
// second position lists it in CATALOG_EXERCISE_EXTRA_PANELS. C285 also removed
// two pictures that showed a different exercise (straddle L-sit drawn as a
// floor straddle, tuck dragon flag drawn as a lying leg raise) and moved
// hanging_leg_raise (legs to the bar) to the toes-to-bar picture.
// C285 (vector batch): pictures drawn by a script from the joint positions
// (scripts/illustrations/vector/), in true profile, with the lesson marked on
// top (line of sight, ring, magnified detail). They replace the hard target
// seen from behind, redraw the tuck dragon flag and cover drills and strength
// moves that had none. Six pictures that showed another position were removed
// (bird dog, plank hip dips, face pull, pigeon, wall soleus, thread the
// needle): no picture until the redraw. A picture that changes ships under a
// NEW file name: the service worker keeps /_next/image for 7 days by URL.
//
// Only exact matches: same position, not just same muscles. Near variants
// (weighted hollow, bent-knee raises, the pistol progression's easier steps)
// stay without an image rather than show a different exercise. Side-specific moves show the
// right-side picture unless the caller knows it is the left side's turn.

const DIR = "/exercises/";

export const CATALOG_EXERCISE_IMAGES: Readonly<Record<string, string>> = {
  core_hollow_hold: "core/01_hollow_body.webp",
  dead_bug: "core/02_dead_bug.webp",
  plank_shoulder_tap: "core/03_plank_shoulder_taps.webp",
  side_plank: "core/10_side_plank_r.webp",
  copenhagen_plank: "core/12_copenhagen_r.webp",
  copenhagen_adductor_plank: "core/12_copenhagen_r.webp",
  v_up: "core/14_v_up.webp",
  glute_bridge: "core/20_glute_bridge.webp",
  lying_windshield_wiper: "core/25_windshield_wipers.webp",
  core_l_sit: "core/26_l_sit_floor.webp",
  test_l_sit_hold: "core/26_l_sit_floor.webp",
  single_leg_glute_bridge: "core/30_sl_glute_bridge.webp",
  front_lever_tuck: "core/32_front_lever_tuck.webp",
  windshield_wipers: "core/33_hanging_wipers.webp",
  side_plank_star: "core/34_star_side_plank_r.webp",
  hanging_leg_raise_horizontal: "core/38_hanging_leg_raise.webp",
  nordic_curl: "core/39_nordic_curl.webp",
  arch_hold: "core/40_arch_body_hold.webp",
  // C281 — stretches
  cooldown_forearm_wrist_stretch: "stretch/stretch_finger_flexor.webp",
  forearm_stretches: "stretch/stretch_finger_flexor.webp",
  cooldown_hamstring_fold: "stretch/stretch_standing_forward_fold.webp",
  cooldown_spinal_twist: "stretch/stretch_supine_twist.webp",
  cooldown_deep_squat_hold: "stretch/stretch_deep_squat.webp",
  cooldown_shoulder_chest: "stretch/stretch_doorway_chest.webp",
  lat_overhead_stretch: "stretch/stretch_lat_triceps.webp",
  hip_flexor_couch_stretch: "stretch/hip_flexor_couch_stretch.webp",
  cooldown_hip_frog: "stretch/cooldown_hip_frog.webp",
  // C282 — strength and prehab moves whose name does not show the position
  front_lever_one_leg: "strength/front_lever_one_leg.webp",
  wall_slide: "strength/wall_slide.webp",
  wall_handstand_hold: "strength/wall_handstand_hold.webp",
  wall_handstand_shrugs: "strength/wall_handstand_hold.webp",
  heel_pulls_chest_to_wall: "strength/heel_pulls_chest_to_wall.webp",
  archer_pullup: "strength/archer_pullup.webp",
  lock_off_isometric: "strength/lock_off_isometric.webp",
  toes_to_bar: "strength/toes_to_bar.webp",
  reverse_wrist_curl: "strength/reverse_wrist_curl.webp",
  wrist_curl: "strength/wrist_curl.webp",
  forearm_pronation_supination: "strength/forearm_pronation_supination.webp",
  bear_crawl: "strength/bear_crawl.webp",
  turkish_getup: "strength/turkish_getup.webp",
  hanging_leg_raise: "strength/toes_to_bar.webp",
  // C285 — exact existing pictures (same position; dynamic variants follow the
  // wall_handstand_shrugs precedent: the picture shows the position they move in)
  pike_pushup: "core/28_pike_pulse.webp",
  plank: "core/05_body_saw.webp",
  rkc_plank: "core/05_body_saw.webp",
  hollow_rock: "core/01_hollow_body.webp",
  copenhagen_dynamic: "core/12_copenhagen_r.webp",
  elbow_wrist_extensor_eccentric: "strength/reverse_wrist_curl.webp",
  test_hip_flexibility: "stretch/stretch_seated_straddle.webp",
  // C285 — technique drills
  twist_lock_drill: "technique/twist_lock_backstep.webp",
  flag_practice: "technique/flag_outside.webp",
  hip_rotation_drill: "technique/hip_rotation.webp",
  tech_hard_target: "technique/hard_target_profile.webp",
  // C285 — vector batch (scripts/illustrations/vector/)
  glued_feet_board: "technique/glued_feet.webp",
  tech_talon_feet: "technique/glued_feet.webp",
  small_feet_press_hold: "technique/small_feet_press.webp",
  rest_and_clip_drill: "technique/kneebar_rest.webp",
  fall_practice: "technique/fall_practice.webp",
  fall_ladder: "technique/fall_practice.webp",
  pocket_rampup_hangboard: "strength/pocket_rampup.webp",
  single_finger_pocket_rampup: "strength/pocket_rampup_mono.webp",
  v_sit: "strength/v_sit.webp",
  v_sit_45: "strength/v_sit_45.webp",
  elevated_pike_pushup: "strength/elevated_pike_pushup.webp",
  ring_fallout: "strength/ring_fallout.webp",
  pistol_squat: "strength/pistol_squat.webp",
  dragon_flag_tuck: "core/41_dragon_flag_tuck.webp",
  dragon_flag_tuck_negative: "core/41_dragon_flag_tuck.webp",
};

/**
 * C285: further panels of a drill whose lesson is more than one position,
 * shown after the main picture in the guided player's How-to.
 */
export const CATALOG_EXERCISE_EXTRA_PANELS: Readonly<Record<string, readonly string[]>> = {
  twist_lock_drill: ["technique/drop_knee.webp"],
};

const LEFT_SIDE: Readonly<Record<string, string>> = {
  "core/10_side_plank_r.webp": "core/11_side_plank_l.webp",
  "core/12_copenhagen_r.webp": "core/13_copenhagen_l.webp",
  "core/34_star_side_plank_r.webp": "core/35_star_side_plank_l.webp",
  "strength/archer_pullup.webp": "strength/archer_pullup_l.webp",
  "strength/reverse_wrist_curl.webp": "strength/reverse_wrist_curl_l.webp",
  "strength/wrist_curl.webp": "strength/wrist_curl_l.webp",
  "strength/forearm_pronation_supination.webp": "strength/forearm_pronation_supination_l.webp",
  "strength/turkish_getup.webp": "strength/turkish_getup_l.webp",
  "strength/pistol_squat.webp": "strength/pistol_squat_l.webp",
  "technique/small_feet_press.webp": "technique/small_feet_press_l.webp",
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

/** C285: every picture of an exercise, main one first; [] when it has none. */
export function exerciseImagePanels(exerciseId: string | null | undefined): string[] {
  const main = exerciseImage(exerciseId);
  if (!main || !exerciseId) return [];
  return [main, ...(CATALOG_EXERCISE_EXTRA_PANELS[exerciseId] ?? []).map((f) => DIR + f)];
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
