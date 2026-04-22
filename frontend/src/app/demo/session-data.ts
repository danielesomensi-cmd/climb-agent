export type Tier = "prep" | "main" | "support";

export interface DemoExercise {
  id: string;
  title: string;
  dosage: string;
  description: string;
  cues: string[];
}

export interface DemoBlock {
  n: string;
  title: string;
  mins: number;
  start: string;
  tier: Tier;
  exercises: DemoExercise[];
}

export const DEMO_SESSION: DemoBlock[] = [
  {
    n: "01",
    title: "Warmup",
    mins: 12,
    start: "08:00",
    tier: "prep",
    exercises: [
      {
        id: "pulse_raise",
        title: "Pulse raise / cardio",
        dosage: "1 × 3 min",
        description:
          "Jumping jacks, skipping, or light jog. Raise heart rate and warm the body up.",
        cues: [
          "Choose jumping jacks, skipping in place, or a light jog.",
          "Aim for a 6–7/10 effort — light sweat is the target.",
          "Keep it continuous for 3 minutes.",
        ],
      },
      {
        id: "joint_circles",
        title: "Joint circles",
        dosage: "1 × 2 min",
        description:
          "Wrists, shoulders, hips, ankles. Slow circles, 10 reps each direction per joint.",
        cues: [
          "Start at the wrists: circles forward and backward, then flexion/extension.",
          "Shoulders: large arm circles, then cross-body hugs.",
          "Hips: big circles, slow and controlled.",
          "Ankles: circles, then point and flex.",
          "Never force range of motion — just explore what's available.",
        ],
      },
      {
        id: "hip_mobility",
        title: "Hip mobility circuit",
        dosage: "2 × 5 reps each",
        description:
          "Hip circles, leg swings (front/back + side), deep lunge with rotation, Cossack squats. Use a band for leg swings if available.",
        cues: [
          "Hip circles: stand on one leg, draw slow circles with the raised knee. 5 each direction, then switch.",
          "Leg swings front/back: hold a wall, swing leg forward and back freely. 10 each leg.",
          "Leg swings side-to-side: same, but lateral. Keep torso upright. 10 each leg.",
          "Deep lunge with rotation: step into a deep lunge, reach the inside arm to the floor, then rotate open toward the ceiling. 5 each side.",
          "Cossack squats: wide stance, shift weight left — right leg extended, then right. Control the descent. 5 each side.",
        ],
      },
      {
        id: "easy_traverse",
        title: "Easy traversing",
        dosage: "3 × 3 min — Rest 1:00",
        description:
          "Boulder 2–3 grades below your max. Focus on smooth movement and quiet feet, not difficulty.",
        cues: [
          "Choose jugs or a beginner area — this is not training yet.",
          "Keep it slow: place your feet precisely before moving hands.",
          "Breathe steadily throughout.",
          "1 minute rest between sets — shake out your forearms.",
        ],
      },
    ],
  },
  {
    n: "02",
    title: "Finger Strength — Max Hangs",
    mins: 10,
    start: "08:12",
    tier: "main",
    exercises: [
      {
        id: "max_hangs",
        title: "Max hangs",
        dosage: "5 × 10s hang — Rest 3:00",
        description:
          "Half crimp, largest comfortable edge. 5 sets × 10s hang, 3 min rest. Add weight or reduce edge size until 10s is genuinely hard.",
        cues: [
          "Your fingers are fresh — this is when you train max finger strength.",
          "Pick an edge where 10 seconds is HARD. If you can hang 15s comfortably, add weight or go smaller.",
          "Half crimp: fingers bent ~90° at the second knuckle. No full crimp.",
          "Full 3 minutes rest between sets — this is strength work, not endurance.",
          "No hangboard? Use a door frame or pull-up bar with the first two finger pads over the top.",
          "Use a resistance band to offload bodyweight if needed — banded max hangs are real training.",
          "Stop immediately if you feel sharp pain in a finger pulley.",
        ],
      },
    ],
  },
  {
    n: "03",
    title: "Weighted Pull-ups",
    mins: 10,
    start: "08:22",
    tier: "main",
    exercises: [
      {
        id: "weighted_pull_ups",
        title: "Weighted pull-ups",
        dosage: "4 × 5 — Rest 3:00",
        description:
          "Add weight so the last rep is hard but controlled. 4 sets × 5 reps, 3 min rest.",
        cues: [
          "Still fresh from the hangboard. Add a weight belt, hold a dumbbell between your feet, or use a weighted backpack.",
          "No weight available? Do slow pull-ups: 3 seconds up, 3 seconds down.",
          "Full range of motion: start from a dead hang, chin clears the bar at the top.",
          "If you have weight, add enough so rep 5 is genuinely hard but controlled.",
          "Keep your core engaged — no kipping or swinging.",
          "3 minutes rest between sets.",
        ],
      },
    ],
  },
  {
    n: "04",
    title: "Projecting — Limit Bouldering",
    mins: 20,
    start: "08:32",
    tier: "main",
    exercises: [
      {
        id: "projecting",
        title: "Limit boulder projecting",
        dosage: "4 × 3 attempts — Rest 3:00",
        description:
          "Pick 4 boulder problems at your limit (hardest grade you can try). 3 attempts per problem, 3 min rest between attempts.",
        cues: [
          "This is NOT volume climbing. Pick problems you CAN'T do yet.",
          "Try hard, rest fully. One bad attempt is fine — learn from it and reset.",
          "Spray walls, Kilter Board, and Tension Board are perfect for this.",
          "3 attempts per problem, then move on — don't grind yourself into the ground on one move.",
          "3 full minutes of rest between attempts. Sit down, breathe, visualize.",
          "Power and skill both come from attempts at your limit — this is the most important block for progress.",
        ],
      },
    ],
  },
  {
    n: "05",
    title: "4×4 Bouldering",
    mins: 20,
    start: "08:52",
    tier: "main",
    exercises: [
      {
        id: "four_by_four",
        title: "4×4 Boulder",
        dosage: "4 × 4 problems — Rest 4:00",
        description:
          "Pick 4 problems 1–2 grades below your max. Climb all 4 back-to-back without rest, then rest 4 min. Repeat 4 times.",
        cues: [
          "Pick 4 problems 1–2 grades below your max — flash-1 level.",
          "Kilter Board and Tension Board work great for this.",
          "Climb all 4 back-to-back without stopping — falls are fine, keep moving.",
          "4 full minutes of rest between rounds: sit down, breathe, shake out.",
          "Focus on moving well on all 4 rounds — not just the first two.",
          "If you can't maintain quality on round 3–4, the problems are too hard.",
        ],
      },
    ],
  },
  {
    n: "06",
    title: "Core Circuit",
    mins: 10,
    start: "09:12",
    tier: "support",
    exercises: [
      {
        id: "core_circuit",
        title: "Core circuit",
        dosage: "3 × see notes — Rest 1:00",
        description:
          "3 rounds: front lever raises or hanging knee raises × 8, side plank × 30s each side, hollow body hold × 30s. 1 min rest between rounds.",
        cues: [
          "Front lever raises: hang from bar, keep legs straight, raise to horizontal and lower slowly. Too hard? Tuck knees to chest instead (hanging knee raises).",
          "Side plank: straight line from head to feet, bottom hip off the ground. 30s per side.",
          "Hollow body hold: lie on your back, lower back pressed into floor, arms overhead, legs slightly raised. Hold 30s.",
          "Move directly from one exercise to the next with no rest within the round.",
          "1 minute rest after completing all three exercises.",
        ],
      },
    ],
  },
  {
    n: "07",
    title: "Antagonist Work",
    mins: 10,
    start: "09:22",
    tier: "support",
    exercises: [
      {
        id: "antagonist_circuit",
        title: "Antagonist circuit",
        dosage: "3 × see notes — Rest 1:00",
        description:
          "3 rounds: push-ups × 12 (or dips), band pull-aparts × 15, reverse wrist curls × 12. 1 min rest between rounds.",
        cues: [
          "Climbing is all pulling — this block balances your shoulders and keeps you injury-free.",
          "Push-ups: chest to floor, elbows at ~45° (not flared). No dipping hips.",
          "No dips bar? Do push-ups from feet or knees — just maintain straight body.",
          "Band pull-aparts: hold a light band at shoulder width, pull apart to full extension at chest height. Squeeze the shoulder blades together.",
          "Reverse wrist curls: forearm on a bench, back of hand facing up, curl the hand upward. Light weight — focus on the movement.",
          "1 minute rest between rounds.",
        ],
      },
    ],
  },
  {
    n: "08",
    title: "Stretching & Cooldown",
    mins: 10,
    start: "09:32",
    tier: "prep",
    exercises: [
      {
        id: "forearm_stretch",
        title: "Forearm flexor + extensor stretch",
        dosage: "2 × 30s each",
        description:
          "Flexor: arm extended, palm down, pull fingers toward you. Extensor: palm up, pull fingers down.",
        cues: [
          "Flexor: arm straight, palm facing down. Use other hand to gently bend wrist downward.",
          "Hold 30s, then switch arms.",
          "Extensor: arm straight, palm facing up. Use other hand to gently pull fingers toward you.",
          "Hold 30s, then switch. You should feel the stretch along the top of the forearm.",
        ],
      },
      {
        id: "shoulder_stretch",
        title: "Shoulder stretch",
        dosage: "2 × 30s each side",
        description: "Cross-body and doorframe. Both sides.",
        cues: [
          "Cross-body: pull one arm across your chest with the opposite hand. 30s per side.",
          "Doorframe: stand in a doorway, place both forearms on the frame at 90°, and lean through gently.",
          "Don't force it — just breathe and let the stretch open.",
        ],
      },
      {
        id: "hip_flexor_stretch",
        title: "Hip flexor stretch",
        dosage: "2 × 30s each side",
        description:
          "Low lunge position. Tuck pelvis under to deepen the stretch.",
        cues: [
          "Step one foot forward into a low lunge — back knee on the ground.",
          "Tuck your pelvis slightly (posterior tilt) to feel the stretch in the front of the back hip.",
          "Hold 30s, breathe, then switch sides.",
          "Raise the back-side arm overhead and lean gently to the opposite side for a deeper stretch.",
        ],
      },
      {
        id: "thoracic_rotation",
        title: "Thoracic spine rotation",
        dosage: "2 × 30s each side",
        description:
          "Seated or on all fours. Rotate from mid-back, not the lower back.",
        cues: [
          "Sit cross-legged. Place one hand behind your head, elbow pointing out.",
          "Rotate the elbow toward the ceiling, leading with your mid-back.",
          "Hold the end range for 30s — your lower back stays still, only the mid-spine rotates.",
          "Switch sides. This opens up thoracic mobility critical for steep climbing.",
        ],
      },
      {
        id: "hamstring_stretch",
        title: "Hamstring stretch",
        dosage: "2 × 30s each side",
        description:
          "Seated forward fold or standing. Keep the back straight — hinge from the hips.",
        cues: [
          "Sit on the floor, one leg extended. Hinge from the hips (not the lower back) and reach toward your foot.",
          "You don't need to touch your toes — just feel the pull in the back of the thigh.",
          "Hold 30s, breathe out into the stretch, then switch legs.",
        ],
      },
      {
        id: "deep_breathing",
        title: "Deep breathing",
        dosage: "1 × 1 min",
        description: "Inhale 4s, hold 4s, exhale 6s. Close your eyes.",
        cues: [
          "Sit or lie down comfortably.",
          "Inhale through the nose for 4 seconds.",
          "Hold for 4 seconds.",
          "Exhale slowly through the mouth for 6 seconds.",
          "Repeat for 1 minute. Session done — great work.",
        ],
      },
    ],
  },
];

export const DEMO_TOTAL_MIN = DEMO_SESSION.reduce(
  (acc, block) => acc + block.mins,
  0,
);
