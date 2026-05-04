// Core Circuit exercise catalog — 39 bodyweight exercises
// Organized by movement pattern for climbing-specific core training

export type MovementPattern =
  | "anti_extension"
  | "anti_rotation"
  | "anti_lateral_flexion"
  | "compression"
  | "extension";

export type ExerciseType = "isometric" | "dynamic";

export type Difficulty = "easy" | "hard";

export interface CircuitExercise {
  id: string;
  name: string;
  description: string;
  pattern: MovementPattern;
  type: ExerciseType;
  difficulty: Difficulty;
  requires_bar: boolean;
  image?: string; // filename in /exercises/core/
}

export const CORE_EXERCISES: CircuitExercise[] = [
  // ── Anti-Extension (front — resist spinal arching) ───────────────────

  {
    id: "ce_hollow_body",
    name: "Hollow Body Hold",
    description: "Lie on back, arms overhead, legs extended and lifted. Press lower back into floor. The fundamental climbing body-tension exercise.",
    pattern: "anti_extension",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "01_hollow_body.jpg",
  },
  {
    id: "ce_dead_bug",
    name: "Dead Bug",
    description: "Lie on back, arms up, knees at 90°. Extend opposite arm and leg while keeping lower back pressed to floor. Alternate sides.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "02_dead_bug.jpg",
  },
  {
    id: "ce_plank_shoulder_taps",
    name: "Plank Shoulder Taps",
    description: "High plank position. Tap opposite shoulder with each hand, alternating. Resist hip rotation — keep hips square.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "03_plank_shoulder_taps.jpg",
  },
  {
    id: "ce_bear_crawl_hold",
    name: "Bear Crawl Hold",
    description: "On all fours, lift knees 2cm off the ground. Hold. If too easy, slowly crawl forward and backward while keeping knees hovering.",
    pattern: "anti_extension",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "04_bear_crawl_hold.jpg",
  },
  {
    id: "ce_body_saw",
    name: "Body Saw",
    description: "Forearm plank. Rock your body forward and backward by pushing with your toes. The further back, the harder it gets.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "05_body_saw.png",
  },
  {
    id: "ce_hollow_flutter",
    name: "Hollow Body Flutter Kicks",
    description: "Hollow body position. Small, fast alternating leg kicks. Arms extended overhead or by sides. 50 seconds of these will burn.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "21_hollow_flutter.png",
  },
  {
    id: "ce_inchworm",
    name: "Inchworm Walk-Out",
    description: "Standing, walk hands out to full plank, then walk feet to hands. Repeat. Core + hamstring stretch + shoulder stability.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "22_inchworm.jpeg",
  },
  {
    id: "ce_plank_army_crawl",
    name: "Plank Army Crawl",
    description: "Forearm plank position. Crawl forward using elbows, dragging feet. Like a leopard. Extreme anti-extension under movement.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "23_plank_army_crawl.jpeg",
  },
  {
    id: "ce_dragon_flag_tuck",
    name: "Dragon Flag (Tuck)",
    description: "Lying on bench/floor, grip behind head, lift body into vertical then slowly lower while maintaining rigid line. Tuck knees to reduce lever. Extreme anti-extension demand.",
    pattern: "anti_extension",
    type: "dynamic",
    difficulty: "hard",
    requires_bar: false,
    image: "31_dragon_flag_tuck.jpeg",
  },
  {
    id: "ce_front_lever_tuck",
    name: "Front Lever Tuck Hold",
    description: "Hang from bar, tuck knees to chest, hold body horizontal. Engages lats, rectus abdominis, transverse abdominis. Gold-standard advanced core exercise.",
    pattern: "anti_extension",
    type: "isometric",
    difficulty: "hard",
    requires_bar: true,
    image: "32_front_lever_tuck.png",
  },

  // ── Anti-Rotation (resist twisting — key for barn-door prevention) ──

  {
    id: "ce_bird_dog",
    name: "Bird Dog",
    description: "On all fours, extend opposite arm and leg. Hold 3-5 seconds, switch sides. Resist any rotation or hip drop.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "06_bird_dog.jpg",
  },
  {
    id: "ce_plank_hip_dips",
    name: "Plank Hip Dips",
    description: "Forearm plank. Rotate hips to tap the floor on each side, alternating. Controlled movement through the obliques.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "07_plank_hip_dips.jpg",
  },
  {
    id: "ce_thread_the_needle",
    name: "Thread the Needle",
    description: "Side plank. Thread your free arm under your torso, then open up fully. Controlled rotation under load.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "08_thread_the_needle.png",
  },
  {
    id: "ce_dead_bug_cross",
    name: "Dead Bug Cross-Body Reach",
    description: "Like dead bug but add elbow-to-opposite-knee touch on the return. Adds rotational component to anti-extension.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "09_dead_bug_cross.png",
  },
  {
    id: "ce_renegade_row_bw",
    name: "Renegade Row (Bodyweight)",
    description: "Push-up position. Lift one straight arm forward, hold 2 seconds, lower. Alternate. No weights needed — the anti-rotation demand is brutal at 50s.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "24_renegade_row_bw.jpeg",
  },
  {
    id: "ce_windshield_wipers",
    name: "Windshield Wipers (Floor)",
    description: "Lie on back, legs vertical. Lower both legs side to side like a windshield wiper. Long lever = devastating for obliques. Control the descent.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "25_windshield_wipers.png",
  },
  {
    id: "ce_hanging_wipers",
    name: "Hanging Windshield Wipers",
    description: "Hang from bar, raise legs to horizontal, rotate side to side. Extreme oblique and anti-rotation demand. No floor equivalent at comparable intensity.",
    pattern: "anti_rotation",
    type: "dynamic",
    difficulty: "hard",
    requires_bar: true,
    image: "33_hanging_wipers.png",
  },

  // ── Anti-Lateral Flexion (sides — resist sideways bending) ──────────

  {
    id: "ce_side_plank_r",
    name: "Side Plank (Right)",
    description: "Right forearm side plank. Stack feet or stagger. Keep hips high, body in a straight line. Hold.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "10_side_plank_r.jpg",
  },
  {
    id: "ce_side_plank_l",
    name: "Side Plank (Left)",
    description: "Left forearm side plank. Stack feet or stagger. Keep hips high, body in a straight line. Hold.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "11_side_plank_l.jpg",
  },
  {
    id: "ce_copenhagen_r",
    name: "Copenhagen Plank (Right)",
    description: "Right side plank with top leg on a chair or bench. Bottom leg hangs free. Adductors + lateral core. Simplified: use knee instead of foot.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "12_copenhagen_r.jpg",
  },
  {
    id: "ce_copenhagen_l",
    name: "Copenhagen Plank (Left)",
    description: "Left side plank with top leg on a chair or bench. Bottom leg hangs free. Adductors + lateral core. Simplified: use knee instead of foot.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "13_copenhagen_l.jpg",
  },
  {
    id: "ce_star_side_plank_r",
    name: "Star Side Plank (Right)",
    description: "Side plank with top arm and top leg both extended/raised. Massively increases lever arm and instability.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "34_star_side_plank_r.jpeg",
  },
  {
    id: "ce_star_side_plank_l",
    name: "Star Side Plank (Left)",
    description: "Side plank with top arm and top leg both extended/raised. Massively increases lever arm and instability.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "35_star_side_plank_l.jpeg",
  },

  // ── Compression / Hip Flexion (critical for toe-hooks, overhanging body tension) ──

  {
    id: "ce_v_up",
    name: "V-Up",
    description: "Lie flat. Simultaneously raise legs and torso to touch toes at the top. Full compression. Lower with control.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "hard",
    requires_bar: false,
    image: "14_v_up.jpg",
  },
  {
    id: "ce_alt_leg_raise",
    name: "Alternating Leg Raise",
    description: "Lie on back, hands under hips. Raise one leg to vertical, lower it while the other goes up. Keep lower back pinned. Scissors motion.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "15_alt_leg_raise.jpg",
  },
  {
    id: "ce_bicycle_crunch",
    name: "Bicycle Crunch",
    description: "Lie on back, hands behind head. Bring elbow to opposite knee while extending the other leg. Lower back stays on floor — this is NOT a sit-up.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "16_bicycle_crunch.webp",
  },
  {
    id: "ce_tuck_up",
    name: "Tuck-Up",
    description: "Lie flat. Pull knees to chest while lifting shoulders off floor. Extend back out. Easier V-up progression.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "17_tuck_up.jpg",
  },
  {
    id: "ce_l_sit_floor",
    name: "L-Sit Hold (Floor)",
    description: "Hands on floor beside hips. Lift body with legs extended forward. If full L-sit is impossible, alternate tuck/extend. Ultimate climbing-specific compression.",
    pattern: "compression",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    image: "26_l_sit_floor.jpeg",
  },
  {
    id: "ce_pike_pulse",
    name: "Pike Pulse",
    description: "Inverted V position (downward dog). Pulse hips upward with small micro-movements. Compression + shoulders. Burns after 20 seconds.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "28_pike_pulse.jpeg",
  },
  {
    id: "ce_straddle_l_sit",
    name: "Straddle L-Sit (Floor)",
    description: "L-sit with legs spread wide in straddle. Requires greater hip flexor strength and compression than regular L-sit.",
    pattern: "compression",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    // image: "36_straddle_l_sit.jpeg", // TODO: add image
  },
  {
    id: "ce_v_up_hold",
    name: "V-Up Hold (Isometric)",
    description: "Hold the top position of a V-up — torso and legs form a V. Sustained compression under isometric tension.",
    pattern: "compression",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    // image: "37_v_up_hold.jpeg", // TODO: add image
  },
  {
    id: "ce_hanging_leg_raise",
    name: "Hanging Leg Raise",
    description: "Hang from bar, raise straight legs to horizontal or above. Scapulae retracted, lats engaged, controlled lowering. Top climbing compression exercise.",
    pattern: "compression",
    type: "dynamic",
    difficulty: "hard",
    requires_bar: true,
    image: "38_hanging_leg_raise.jpeg",
  },

  // ── Extension / Posterior Chain (anti-climber's-back — often neglected!) ──

  {
    id: "ce_superman_hold",
    name: "Superman Hold",
    description: "Lie face down. Lift arms and legs off the floor simultaneously. Hold. Erector spinae + glutes. Essential counterbalance to climbing's pulling pattern.",
    pattern: "extension",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "18_superman_hold.jpg",
  },
  {
    id: "ce_superman_swimmers",
    name: "Superman Swimmers",
    description: "Superman position but alternate arm and leg like swimming. Dynamic, coordination. Keep chest and thighs off floor throughout.",
    pattern: "extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "19_superman_swimmers.jpg",
  },
  {
    id: "ce_glute_bridge",
    name: "Glute Bridge Hold",
    description: "Lie on back, feet flat on floor. Lift hips until body is straight from shoulders to knees. Squeeze glutes hard at top. Hold.",
    pattern: "extension",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "20_glute_bridge.jpeg",
  },
  {
    id: "ce_reverse_plank",
    name: "Reverse Plank",
    description: "Hands on floor behind you, legs straight. Lift hips until body is straight. Hold. Full posterior chain + chest opener. Anti-kyphosis.",
    pattern: "extension",
    type: "isometric",
    difficulty: "easy",
    requires_bar: false,
    image: "29_reverse_plank.jpeg",
  },
  {
    id: "ce_sl_glute_bridge",
    name: "Single-Leg Glute Bridge (Alternating)",
    description: "Glute bridge on one leg. Other leg extended. Alternate every 5 reps or every 10 seconds. Unilateral = much harder. Glutes + pelvic stabilization.",
    pattern: "extension",
    type: "dynamic",
    difficulty: "easy",
    requires_bar: false,
    image: "30_sl_glute_bridge.png",
  },
  {
    id: "ce_nordic_curl",
    name: "Nordic Curl",
    description: "Kneeling, feet anchored, slowly lower torso forward keeping hips extended. Control the eccentric. The #1 hamstring/posterior chain exercise per literature.",
    pattern: "extension",
    type: "dynamic",
    difficulty: "hard",
    requires_bar: false,
    image: "39_nordic_curl.jpeg",
  },
  {
    id: "ce_arch_body_hold",
    name: "Arch Body Hold",
    description: "Prone, arms overhead, lift arms and legs off floor simultaneously. Reverse hollow body — trains erector spinae, glutes, posterior chain as a unit.",
    pattern: "extension",
    type: "isometric",
    difficulty: "hard",
    requires_bar: false,
    // image: "40_arch_body_hold.jpeg", // TODO: add image
  },
];

export interface CircuitSelectionConfig {
  difficulty: Difficulty;
  hasBar: boolean;
}

/**
 * Generate a randomized circuit sequence with difficulty-based 80/20 split.
 *
 * 1. Filter out bar exercises if !hasBar
 * 2. Split into easy/hard pools
 * 3. Allocate 80% from chosen difficulty, 20% from the other
 * 4. Cap to available pool sizes, fill remainder from the other pool
 * 5. Shuffle and merge
 */
export function generateCircuitSequence(
  pool: CircuitExercise[],
  count: number,
  config?: CircuitSelectionConfig
): CircuitExercise[] {
  if (pool.length === 0 || count <= 0) return [];

  const fisherYates = (arr: CircuitExercise[]): CircuitExercise[] => {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };

  // If no config provided, use legacy behavior (full pool, no filtering)
  if (!config) {
    const shuffled = fisherYates(pool);
    return shuffled.slice(0, Math.min(count, pool.length));
  }

  // Step 1: filter bar exercises
  const filtered = config.hasBar ? pool : pool.filter((e) => !e.requires_bar);
  if (filtered.length === 0) return [];

  // Step 2: split by difficulty
  const easyPool = filtered.filter((e) => e.difficulty === "easy");
  const hardPool = filtered.filter((e) => e.difficulty === "hard");

  // Step 3: allocate 80/20
  let primaryCount: number;
  let secondaryCount: number;
  let primaryPool: CircuitExercise[];
  let secondaryPool: CircuitExercise[];

  if (config.difficulty === "hard") {
    primaryPool = hardPool;
    secondaryPool = easyPool;
  } else {
    primaryPool = easyPool;
    secondaryPool = hardPool;
  }

  primaryCount = Math.round(count * 0.8);
  secondaryCount = count - primaryCount;

  // Step 4: cap to available pool sizes
  if (primaryCount > primaryPool.length) {
    primaryCount = primaryPool.length;
    secondaryCount = Math.min(count - primaryCount, secondaryPool.length);
  } else if (secondaryCount > secondaryPool.length) {
    secondaryCount = secondaryPool.length;
    primaryCount = Math.min(count - secondaryCount, primaryPool.length);
  }

  // Step 5: shuffle each pool and pick
  const pickedPrimary = fisherYates(primaryPool).slice(0, primaryCount);
  const pickedSecondary = fisherYates(secondaryPool).slice(0, secondaryCount);

  // Step 6: merge and shuffle
  return fisherYates([...pickedPrimary, ...pickedSecondary]);
}
