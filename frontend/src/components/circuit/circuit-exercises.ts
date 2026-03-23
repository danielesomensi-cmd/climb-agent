// Core Circuit exercise catalog — 30 bodyweight exercises
// Organized by movement pattern for climbing-specific core training

export type MovementPattern =
  | "anti_extension"
  | "anti_rotation"
  | "anti_lateral_flexion"
  | "compression"
  | "extension";

export type ExerciseType = "isometric" | "dynamic";

export interface CircuitExercise {
  id: string;
  name: string;
  description: string;
  pattern: MovementPattern;
  type: ExerciseType;
  advanced: boolean;
  image?: string; // filename in /exercises/core/
}

export const CORE_EXERCISES: CircuitExercise[] = [
  // 3.1 Anti-Extension (front — resist spinal arching)
  {
    id: "ce_hollow_body",
    name: "Hollow Body Hold",
    description: "Lie on back, arms overhead, legs extended and lifted. Press lower back into floor. The fundamental climbing body-tension exercise.",
    pattern: "anti_extension",
    type: "isometric",
    advanced: false,
    image: "01_hollow_body.png.jpg",
  },
  {
    id: "ce_dead_bug",
    name: "Dead Bug",
    description: "Lie on back, arms up, knees at 90°. Extend opposite arm and leg while keeping lower back pressed to floor. Alternate sides.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: false,
    image: "02_dead_bug.png.jpg",
  },
  {
    id: "ce_plank_shoulder_taps",
    name: "Plank Shoulder Taps",
    description: "High plank position. Tap opposite shoulder with each hand, alternating. Resist hip rotation — keep hips square.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: false,
    image: "03_plank_shoulder_taps.png.jpg",
  },
  {
    id: "ce_bear_crawl_hold",
    name: "Bear Crawl Hold",
    description: "On all fours, lift knees 2cm off the ground. Hold. If too easy, slowly crawl forward and backward while keeping knees hovering.",
    pattern: "anti_extension",
    type: "isometric",
    advanced: false,
    image: "04_bear_crawl_hold.png.jpg",
  },
  {
    id: "ce_body_saw",
    name: "Body Saw",
    description: "Forearm plank. Rock your body forward and backward by pushing with your toes. The further back, the harder it gets.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: false,
    image: "05_body_saw.png",
  },

  // 3.2 Anti-Rotation (resist twisting — key for barn-door prevention)
  {
    id: "ce_bird_dog",
    name: "Bird Dog",
    description: "On all fours, extend opposite arm and leg. Hold 3-5 seconds, switch sides. Resist any rotation or hip drop.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: false,
    image: "06_bird_dog.png.jpg",
  },
  {
    id: "ce_plank_hip_dips",
    name: "Plank Hip Dips",
    description: "Forearm plank. Rotate hips to tap the floor on each side, alternating. Controlled movement through the obliques.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: false,
  },
  {
    id: "ce_thread_the_needle",
    name: "Thread the Needle",
    description: "Side plank. Thread your free arm under your torso, then open up fully. Controlled rotation under load.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: false,
    image: "08_thread_the_needle.png",
  },
  {
    id: "ce_dead_bug_cross",
    name: "Dead Bug Cross-Body Reach",
    description: "Like dead bug but add elbow-to-opposite-knee touch on the return. Adds rotational component to anti-extension.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: false,
  },

  // 3.3 Anti-Lateral Flexion (sides — resist sideways bending)
  {
    id: "ce_side_plank_r",
    name: "Side Plank (Right)",
    description: "Right forearm side plank. Stack feet or stagger. Keep hips high, body in a straight line. Hold.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    advanced: false,
  },
  {
    id: "ce_side_plank_l",
    name: "Side Plank (Left)",
    description: "Left forearm side plank. Same cues as right side.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    advanced: false,
  },
  {
    id: "ce_copenhagen_r",
    name: "Copenhagen Plank (Right)",
    description: "Right side plank with top leg on a chair or bench. Bottom leg hangs free. Adductors + lateral core. Simplified: use knee instead of foot.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    advanced: false,
  },
  {
    id: "ce_copenhagen_l",
    name: "Copenhagen Plank (Left)",
    description: "Left side Copenhagen plank. Same cues as right side.",
    pattern: "anti_lateral_flexion",
    type: "isometric",
    advanced: false,
  },

  // 3.4 Compression / Hip Flexion (critical for toe-hooks, overhanging body tension)
  {
    id: "ce_v_up",
    name: "V-Up",
    description: "Lie flat. Simultaneously raise legs and torso to touch toes at the top. Full compression. Lower with control.",
    pattern: "compression",
    type: "dynamic",
    advanced: false,
  },
  {
    id: "ce_alt_leg_raise",
    name: "Alternating Leg Raise",
    description: "Lie on back, hands under hips. Raise one leg to vertical, lower it while the other goes up. Keep lower back pinned. Scissors motion.",
    pattern: "compression",
    type: "dynamic",
    advanced: false,
  },
  {
    id: "ce_bicycle_crunch",
    name: "Bicycle Crunch",
    description: "Lie on back, hands behind head. Bring elbow to opposite knee while extending the other leg. Lower back stays on floor — this is NOT a sit-up.",
    pattern: "compression",
    type: "dynamic",
    advanced: false,
  },
  {
    id: "ce_tuck_up",
    name: "Tuck-Up",
    description: "Lie flat. Pull knees to chest while lifting shoulders off floor. Extend back out. Easier V-up progression.",
    pattern: "compression",
    type: "dynamic",
    advanced: false,
  },

  // 3.5 Extension / Posterior Chain (anti-climber's-back — often neglected!)
  {
    id: "ce_superman_hold",
    name: "Superman Hold",
    description: "Lie face down. Lift arms and legs off the floor simultaneously. Hold. Erector spinae + glutes. Essential counterbalance to climbing's pulling pattern.",
    pattern: "extension",
    type: "isometric",
    advanced: false,
  },
  {
    id: "ce_superman_swimmers",
    name: "Superman Swimmers",
    description: "Superman position but alternate arm and leg like swimming. Dynamic, coordination. Keep chest and thighs off floor throughout.",
    pattern: "extension",
    type: "dynamic",
    advanced: false,
  },
  {
    id: "ce_glute_bridge",
    name: "Glute Bridge Hold",
    description: "Lie on back, feet flat on floor. Lift hips until body is straight from shoulders to knees. Squeeze glutes hard at top. Hold.",
    pattern: "extension",
    type: "isometric",
    advanced: false,
  },

  // 3.6 Advanced — Anti-Extension
  {
    id: "ce_hollow_flutter",
    name: "Hollow Body Flutter Kicks",
    description: "Hollow body position. Small, fast alternating leg kicks. Arms extended overhead or by sides. 50 seconds of these will burn.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: true,
  },
  {
    id: "ce_inchworm",
    name: "Inchworm Walk-Out",
    description: "Standing, walk hands out to full plank, then walk feet to hands. Repeat. Core + hamstring stretch + shoulder stability.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: true,
  },
  {
    id: "ce_plank_army_crawl",
    name: "Plank Army Crawl",
    description: "Forearm plank position. Crawl forward using elbows, dragging feet. Like a leopard. Extreme anti-extension under movement.",
    pattern: "anti_extension",
    type: "dynamic",
    advanced: true,
  },

  // 3.7 Advanced — Anti-Rotation
  {
    id: "ce_renegade_row_bw",
    name: "Renegade Row (Bodyweight)",
    description: "Push-up position. Lift one straight arm forward, hold 2 seconds, lower. Alternate. No weights needed — the anti-rotation demand is brutal at 50s.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: true,
  },
  {
    id: "ce_windshield_wipers",
    name: "Windshield Wipers (Floor)",
    description: "Lie on back, legs vertical. Lower both legs side to side like a windshield wiper. Long lever = devastating for obliques. Control the descent.",
    pattern: "anti_rotation",
    type: "dynamic",
    advanced: true,
  },

  // 3.8 Advanced — Compression
  {
    id: "ce_l_sit_floor",
    name: "L-Sit Hold (Floor)",
    description: "Hands on floor beside hips. Lift body with legs extended forward. If full L-sit is impossible, alternate tuck/extend. Ultimate climbing-specific compression.",
    pattern: "compression",
    type: "isometric",
    advanced: true,
  },
  {
    id: "ce_toes_to_hands",
    name: "Toes-to-Hands",
    description: "Lie flat. Bring toes to hands above your head, lifting torso to meet them. Full range V-up with tight pike. Maximum compression.",
    pattern: "compression",
    type: "dynamic",
    advanced: true,
  },
  {
    id: "ce_pike_pulse",
    name: "Pike Pulse",
    description: "Inverted V position (downward dog). Pulse hips upward with small micro-movements. Compression + shoulders. Burns after 20 seconds.",
    pattern: "compression",
    type: "dynamic",
    advanced: true,
  },

  // 3.9 Advanced — Posterior Chain
  {
    id: "ce_reverse_plank",
    name: "Reverse Plank",
    description: "Hands on floor behind you, legs straight. Lift hips until body is straight. Hold. Full posterior chain + chest opener. Anti-kyphosis.",
    pattern: "extension",
    type: "isometric",
    advanced: true,
  },
  {
    id: "ce_sl_glute_bridge",
    name: "Single-Leg Glute Bridge (Alternating)",
    description: "Glute bridge on one leg. Other leg extended. Alternate every 5 reps or every 10 seconds. Unilateral = much harder. Glutes + pelvic stabilization.",
    pattern: "extension",
    type: "dynamic",
    advanced: true,
  },
];

/**
 * Generate a randomized circuit sequence using Fisher-Yates shuffle.
 * Guarantees no two consecutive exercises are the same when pool is exhausted and reshuffled.
 */
export function generateCircuitSequence(
  pool: CircuitExercise[],
  count: number
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

  const shuffled = fisherYates(pool);

  if (count <= pool.length) {
    return shuffled.slice(0, count);
  }

  // If count > pool size, cycle through reshuffled pool
  // Guarantee: no two consecutive exercises are the same
  const sequence = [...shuffled];
  while (sequence.length < count) {
    const reshuffled = fisherYates(pool);
    // Avoid last exercise of previous batch === first of new batch
    if (reshuffled[0].id === sequence[sequence.length - 1].id && reshuffled.length > 1) {
      [reshuffled[0], reshuffled[1]] = [reshuffled[1], reshuffled[0]];
    }
    sequence.push(...reshuffled);
  }
  return sequence.slice(0, count);
}
