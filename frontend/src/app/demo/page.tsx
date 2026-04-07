"use client";

import { useState } from "react";
import Link from "next/link";
import { ExerciseCard } from "@/components/training/exercise-card";
import { ExerciseTimer } from "@/components/guided/exercise-timer";
import { Button } from "@/components/ui/button";
import { Timer, ChevronDown, ChevronUp, ArrowRight } from "lucide-react";

// ---------------------------------------------------------------------------
// Demo session data — English, ~100 min, generic 6b–7a gym climber
// ---------------------------------------------------------------------------

interface DemoExercise {
  card: {
    exercise_id: string;
    name: string;
    sets?: number;
    reps?: string;
    load_kg?: number;
    rest_s?: number;
    notes?: string;
  };
  cues: string[];
  timer: {
    workSeconds: number;
    restBetweenRepsSeconds: number;
    restBetweenSetsSeconds: number;
    sets: number;
    reps: number;
    altSides?: boolean;
  } | null;
}

interface DemoBlock {
  id: string;
  label: string;
  moduleRole: string;
  durationLabel: string;
  exercises: DemoExercise[];
}

const DEMO_BLOCKS: DemoBlock[] = [
  // -------------------------------------------------------------------------
  // 1. Warmup (~12 min)
  // -------------------------------------------------------------------------
  {
    id: "warmup",
    label: "Warmup",
    moduleRole: "warmup_general",
    durationLabel: "~12 min",
    exercises: [
      {
        card: {
          exercise_id: "pulse_raise",
          name: "Pulse raise / cardio",
          sets: 1,
          reps: "3 min",
          notes: "Jumping jacks, skipping, or light jog. Goal: raise heart rate and warm the body up.",
        },
        cues: [
          "Choose jumping jacks, skipping in place, or a light jog.",
          "Aim for a 6–7/10 effort — light sweat is the target.",
          "Keep it continuous for 3 minutes.",
        ],
        timer: {
          workSeconds: 180,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 0,
          sets: 1,
          reps: 1,
        },
      },
      {
        card: {
          exercise_id: "joint_circles",
          name: "Joint circles",
          sets: 1,
          reps: "2 min",
          notes: "Wrists, shoulders, hips, ankles. Slow circles, 10 reps each direction per joint.",
        },
        cues: [
          "Start at the wrists: circles forward and backward, then flexion/extension.",
          "Shoulders: large arm circles, then cross-body hugs.",
          "Hips: big circles, slow and controlled.",
          "Ankles: circles, then point and flex.",
          "Never force range of motion — just explore what's available.",
        ],
        timer: {
          workSeconds: 120,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 0,
          sets: 1,
          reps: 1,
        },
      },
      {
        card: {
          exercise_id: "hip_mobility",
          name: "Hip mobility circuit",
          sets: 2,
          reps: "5 reps each",
          notes: "Hip circles, leg swings (front/back + side), deep lunge with rotation, Cossack squats. Use a band for leg swings if available.",
        },
        cues: [
          "Hip circles: stand on one leg, draw slow circles with the raised knee. 5 each direction, then switch.",
          "Leg swings front/back: hold a wall, swing leg forward and back freely. 10 each leg.",
          "Leg swings side-to-side: same, but lateral. Keep torso upright. 10 each leg.",
          "Deep lunge with rotation: step into a deep lunge, reach the inside arm to the floor, then rotate open toward the ceiling. 5 each side.",
          "Cossack squats: wide stance, shift weight left — right leg extended, then right. Control the descent. 5 each side.",
        ],
        timer: null,
      },
      {
        card: {
          exercise_id: "easy_traverse",
          name: "Easy traversing",
          sets: 3,
          reps: "3 min",
          rest_s: 60,
          notes: "Boulder 2–3 grades below your max. Focus on smooth movement and quiet feet, not difficulty.",
        },
        cues: [
          "Choose jugs or a beginner area — this is not training yet.",
          "Keep it slow: place your feet precisely before moving hands.",
          "Breathe steadily throughout.",
          "1 minute rest between sets — shake out your forearms.",
        ],
        timer: {
          workSeconds: 180,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 60,
          sets: 3,
          reps: 1,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 2. 4×4 Bouldering (~20 min)
  // -------------------------------------------------------------------------
  {
    id: "main_4x4",
    label: "4×4 Bouldering",
    moduleRole: "main_set",
    durationLabel: "~20 min",
    exercises: [
      {
        card: {
          exercise_id: "four_by_four",
          name: "4×4 Boulder",
          sets: 4,
          reps: "4 problems",
          rest_s: 240,
          notes: "Pick 4 problems 1–2 grades below your flash level. Climb all 4 without rest, then rest 4 min. Repeat 4 times.",
        },
        cues: [
          "Choose 4 problems you can flash or nearly flash.",
          "Spray walls, Kilter Board, and Tension Board are perfect for this.",
          "Climb all 4 back-to-back without stopping — falls are fine, keep moving.",
          "4 full minutes of rest between rounds: sit down, breathe, shake out.",
          "Focus on moving well on all 4 rounds — not just the first two.",
          "If you can't maintain quality on round 3–4, the problems are too hard.",
        ],
        timer: {
          workSeconds: 0,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 240,
          sets: 4,
          reps: 4,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 3. Free Climbing / Exploration (~20 min)
  // -------------------------------------------------------------------------
  {
    id: "free_climbing",
    label: "Free Climbing / Exploration",
    moduleRole: "main_set",
    durationLabel: "~20 min",
    exercises: [
      {
        card: {
          exercise_id: "free_climbing",
          name: "Open bouldering at flash level",
          sets: 1,
          reps: "20 min",
          notes: "Try new problems, explore different styles. No structure — just climb what looks fun.",
        },
        cues: [
          "Pick problems at or slightly above your flash level.",
          "Try things that look different from what you usually do — slopers, compression, heel hooks.",
          "This is your playground time — have fun, but stay intentional.",
          "If you find something you can't do, spend 5 min on it before moving on.",
          "Stop 5 minutes before the timer ends and shake out before the next block.",
        ],
        timer: {
          workSeconds: 1200,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 0,
          sets: 1,
          reps: 1,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 4. Weighted Pull-ups (~10 min)
  // -------------------------------------------------------------------------
  {
    id: "pull_ups",
    label: "Weighted Pull-ups",
    moduleRole: "main_set",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "weighted_pull_ups",
          name: "Weighted pull-ups",
          sets: 4,
          reps: "5",
          rest_s: 120,
          notes: "Add weight so the last rep is hard but controlled. No weight? Do slow pull-ups (3s up, 3s down).",
        },
        cues: [
          "Full range of motion: start from a dead hang, chin clears the bar at the top.",
          "No weight available? Slow pull-ups: 3 seconds up, 1 second hold, 3 seconds down.",
          "If you have a weight belt or vest, add enough so rep 5 is genuinely hard.",
          "Keep your core engaged — no kipping or swinging.",
          "2 minutes rest between sets.",
        ],
        timer: {
          workSeconds: 0,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 120,
          sets: 4,
          reps: 5,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 5. Core Circuit (~10 min)
  // -------------------------------------------------------------------------
  {
    id: "core",
    label: "Core Circuit",
    moduleRole: "main_set",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "core_circuit",
          name: "Core circuit",
          sets: 3,
          reps: "see notes",
          rest_s: 60,
          notes: "3 rounds: front lever raises or hanging knee raises × 8, side plank × 30s each side, hollow body hold × 30s. 1 min rest between rounds.",
        },
        cues: [
          "Front lever raises: hang from bar, keep legs straight, raise to horizontal and lower slowly. Too hard? Tuck knees to chest instead (hanging knee raises).",
          "Side plank: straight line from head to feet, bottom hip off the ground. 30s per side.",
          "Hollow body hold: lie on your back, lower back pressed into floor, arms overhead, legs slightly raised. Hold 30s.",
          "Move directly from one exercise to the next with no rest within the round.",
          "1 minute rest after completing all three exercises.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 60,
          sets: 3,
          reps: 3,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 6. Hangboard Repeaters (~10 min)
  // -------------------------------------------------------------------------
  {
    id: "hangboard",
    label: "Finger Strength — Hangboard",
    moduleRole: "main_set",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "hangboard_repeaters",
          name: "Hangboard repeaters",
          sets: 3,
          reps: "6 reps × 7s on / 3s off",
          rest_s: 120,
          notes: "Half crimp. Use the largest edge where you feel tension but no pain.",
        },
        cues: [
          "Half crimp: fingers bent ~90° at the second knuckle. Never full crimp when tired.",
          "7 seconds on the hold — keep tension throughout, don't let it go slack.",
          "3 seconds off — release the hold but stay close. Don't sit down between reps.",
          "6 reps = 1 set. 2 minutes full rest between sets.",
          "No hangboard? Use a door frame or pull-up bar with two fingers over the top.",
          "Using a resistance band to reduce weight is real training — don't skip the exercise.",
          "Stop immediately if you feel sharp pain in a finger pulley.",
        ],
        timer: {
          workSeconds: 7,
          restBetweenRepsSeconds: 3,
          restBetweenSetsSeconds: 120,
          sets: 3,
          reps: 6,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 7. Antagonist Work (~10 min)
  // -------------------------------------------------------------------------
  {
    id: "antagonist",
    label: "Antagonist Work",
    moduleRole: "main_set",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "antagonist_circuit",
          name: "Antagonist circuit",
          sets: 3,
          reps: "see notes",
          rest_s: 60,
          notes: "3 rounds: push-ups × 12 (or dips), band pull-aparts × 15, reverse wrist curls × 12. 1 min rest between rounds.",
        },
        cues: [
          "Climbing is all pulling — this block balances your shoulders and keeps you injury-free.",
          "Push-ups: chest to floor, elbows at ~45° (not flared). No dipping hips.",
          "No dips bar? Do push-ups from feet or knees — just maintain straight body.",
          "Band pull-aparts: hold a light band at shoulder width, pull apart to full extension at chest height. Squeeze the shoulder blades together.",
          "Reverse wrist curls: forearm on a bench, back of hand facing up, curl the hand upward. Light weight — focus on the movement.",
          "1 minute rest between rounds.",
        ],
        timer: {
          workSeconds: 0,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 60,
          sets: 3,
          reps: 3,
        },
      },
    ],
  },

  // -------------------------------------------------------------------------
  // 8. Cooldown / Stretching (~10 min)
  // -------------------------------------------------------------------------
  {
    id: "cooldown",
    label: "Stretching & Cooldown",
    moduleRole: "cooldown",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "forearm_stretch",
          name: "Forearm flexor + extensor stretch",
          sets: 2,
          reps: "30s each",
          notes: "Flexor: arm extended, palm down, pull fingers toward you. Extensor: palm up, pull fingers down.",
        },
        cues: [
          "Flexor: arm straight, palm facing down. Use other hand to gently bend wrist downward.",
          "Hold 30s, then switch arms.",
          "Extensor: arm straight, palm facing up. Use other hand to gently pull fingers toward you.",
          "Hold 30s, then switch. You should feel the stretch along the top of the forearm.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 5,
          sets: 2,
          reps: 1,
          altSides: true,
        },
      },
      {
        card: {
          exercise_id: "shoulder_stretch",
          name: "Shoulder stretch",
          sets: 2,
          reps: "30s each side",
          notes: "Cross-body and doorframe. Both sides.",
        },
        cues: [
          "Cross-body: pull one arm across your chest with the opposite hand. 30s per side.",
          "Doorframe: stand in a doorway, place both forearms on the frame at 90°, and lean through gently.",
          "Don't force it — just breathe and let the stretch open.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 5,
          sets: 2,
          reps: 1,
          altSides: true,
        },
      },
      {
        card: {
          exercise_id: "hip_flexor_stretch",
          name: "Hip flexor stretch",
          sets: 2,
          reps: "30s each side",
          notes: "Low lunge position. Tuck pelvis under to deepen the stretch.",
        },
        cues: [
          "Step one foot forward into a low lunge — back knee on the ground.",
          "Tuck your pelvis slightly (posterior tilt) to feel the stretch in the front of the back hip.",
          "Hold 30s, breathe, then switch sides.",
          "Raise the back-side arm overhead and lean gently to the opposite side for a deeper stretch.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 5,
          sets: 2,
          reps: 1,
          altSides: true,
        },
      },
      {
        card: {
          exercise_id: "thoracic_rotation",
          name: "Thoracic spine rotation",
          sets: 2,
          reps: "30s each side",
          notes: "Seated or on all fours. Rotate from mid-back, not the lower back.",
        },
        cues: [
          "Sit cross-legged. Place one hand behind your head, elbow pointing out.",
          "Rotate the elbow toward the ceiling, leading with your mid-back.",
          "Hold the end range for 30s — your lower back stays still, only the mid-spine rotates.",
          "Switch sides. This opens up thoracic mobility critical for steep climbing.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 5,
          sets: 2,
          reps: 1,
          altSides: true,
        },
      },
      {
        card: {
          exercise_id: "hamstring_stretch",
          name: "Hamstring stretch",
          sets: 2,
          reps: "30s each side",
          notes: "Seated forward fold or standing. Keep the back straight — hinge from the hips.",
        },
        cues: [
          "Sit on the floor, one leg extended. Hinge from the hips (not the lower back) and reach toward your foot.",
          "You don't need to touch your toes — just feel the pull in the back of the thigh.",
          "Hold 30s, breathe out into the stretch, then switch legs.",
        ],
        timer: {
          workSeconds: 30,
          restBetweenRepsSeconds: 5,
          restBetweenSetsSeconds: 5,
          sets: 2,
          reps: 1,
          altSides: true,
        },
      },
      {
        card: {
          exercise_id: "deep_breathing",
          name: "Deep breathing",
          sets: 1,
          reps: "1 min",
          notes: "Inhale 4s, hold 4s, exhale 6s. Close your eyes.",
        },
        cues: [
          "Sit or lie down comfortably.",
          "Inhale through the nose for 4 seconds.",
          "Hold for 4 seconds.",
          "Exhale slowly through the mouth for 6 seconds.",
          "Repeat for 1 minute. Session done — great work.",
        ],
        timer: {
          workSeconds: 60,
          restBetweenRepsSeconds: 0,
          restBetweenSetsSeconds: 0,
          sets: 1,
          reps: 1,
        },
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const CTA_CARD = (
  <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-center space-y-3 my-6">
    <p className="text-sm font-medium text-foreground">
      Your personalized plan is different from this — calibrated to you.
    </p>
    <p className="text-xs text-muted-foreground">
      Your grades, goals, available gym days, and equipment. All computed in 5 minutes.
    </p>
    <Link href="/onboarding/welcome">
      <Button size="sm" className="gap-2">
        Build your free plan
        <ArrowRight className="size-3.5" />
      </Button>
    </Link>
  </div>
);

function ExerciseRow({ ex, moduleRole }: { ex: DemoExercise; moduleRole: string }) {
  const [timerOpen, setTimerOpen] = useState(false);
  const [cuesOpen, setCuesOpen] = useState(false);

  return (
    <div className="space-y-2">
      <ExerciseCard exercise={ex.card} moduleRole={moduleRole} />

      {/* Cues accordion */}
      {ex.cues.length > 0 && (
        <div>
          <button
            onClick={() => setCuesOpen((o) => !o)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-1"
          >
            {cuesOpen ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
            {cuesOpen ? "Hide cues" : "Show cues"}
          </button>
          {cuesOpen && (
            <ul className="mt-2 space-y-1 pl-3 border-l border-border">
              {ex.cues.map((cue, i) => (
                <li key={i} className="text-xs text-muted-foreground leading-relaxed">
                  {cue}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Timer toggle */}
      {ex.timer && (
        <div>
          <button
            onClick={() => setTimerOpen((o) => !o)}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors px-1"
          >
            <Timer className="size-3" />
            {timerOpen ? "Close timer" : "Use timer"}
          </button>
          {timerOpen && (
            <div className="mt-3">
              <ExerciseTimer
                workSeconds={ex.timer.workSeconds}
                restBetweenRepsSeconds={ex.timer.restBetweenRepsSeconds}
                restBetweenSetsSeconds={ex.timer.restBetweenSetsSeconds}
                sets={ex.timer.sets}
                reps={ex.timer.reps}
                altSides={ex.timer.altSides}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BlockSection({
  block,
  showCtaAfter,
}: {
  block: DemoBlock;
  showCtaAfter: boolean;
}) {
  return (
    <section className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-foreground">{block.label}</h2>
        <span className="text-xs text-muted-foreground">{block.durationLabel}</span>
      </div>
      <div className="space-y-3">
        {block.exercises.map((ex) => (
          <ExerciseRow key={ex.card.exercise_id} ex={ex} moduleRole={block.moduleRole} />
        ))}
      </div>
      {showCtaAfter && CTA_CARD}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-background pb-32">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-3">
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-bold text-amber-400 tracking-wide uppercase">
              Demo
            </span>
            <span className="text-sm font-medium text-foreground">Gym session</span>
          </div>
          <span className="text-xs text-muted-foreground">~100 min</span>
        </div>
      </div>

      {/* Intro banner */}
      <div className="mx-auto max-w-3xl px-4 pt-5 pb-2">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-1.5">
          <p className="text-sm font-semibold text-amber-400">
            Sample session for intermediate climbers (6b–7a)
          </p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Your real plan will be different — built around your grades, goals, available days, and gym.
            This demo shows the experience you&apos;ll get every session.
          </p>
        </div>
      </div>

      {/* Session blocks */}
      <div className="mx-auto max-w-3xl px-4 space-y-8 mt-6">
        {DEMO_BLOCKS.map((block) => (
          <BlockSection
            key={block.id}
            block={block}
            showCtaAfter={block.id === "hangboard"}
          />
        ))}

        {/* Final message */}
        <div className="text-center space-y-2 pt-4 pb-2">
          <p className="text-sm font-medium text-foreground">Session complete. Great work.</p>
          <p className="text-xs text-muted-foreground">
            Every session in your real plan includes feedback tracking, automatic load adaptation, and week-over-week progression.
          </p>
        </div>
      </div>

      {/* Sticky CTA bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <div className="mx-auto max-w-3xl flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground leading-snug">
            Want a plan built for you?
          </p>
          <Link href="/onboarding/welcome" className="shrink-0">
            <Button size="sm" className="gap-1.5">
              Start free
              <ArrowRight className="size-3.5" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
