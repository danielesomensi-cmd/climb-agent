"use client";

import { useState } from "react";
import Link from "next/link";
import { ExerciseCard } from "@/components/training/exercise-card";
import { ExerciseTimer } from "@/components/guided/exercise-timer";
import { Button } from "@/components/ui/button";
import { Timer, ChevronDown, ChevronUp, ArrowRight } from "lucide-react";

// ---------------------------------------------------------------------------
// Demo session data — hardcoded for a generic 6b–7a gym climber
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
  {
    id: "warmup",
    label: "Warmup",
    moduleRole: "warmup_general",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "joint_circles",
          name: "Mobilizzazione articolare",
          sets: 1,
          reps: "3 min",
          notes: "Spalle, polsi, dita, anche. Cerchi lenti, 10 rep per articolazione.",
        },
        cues: [
          "Inizia dalle spalle: cerchi in avanti e indietro.",
          "Polsi: cerchi, flessioni, estensioni.",
          "Dita: apri e chiudi a pugno lentamente — non forzare.",
          "Anche: cerchi e affondo laterale.",
        ],
        timer: null,
      },
      {
        card: {
          exercise_id: "easy_traverse",
          name: "Traversata su boulder facile",
          sets: 3,
          reps: "3 min",
          rest_s: 60,
          notes: "Scegli boulder 2–3 gradi sotto il tuo max. Focus: fluidità, non forza.",
        },
        cues: [
          "Usa prese grosse o boulder da principianti.",
          "Muoviti lentamente — non importa se scivoli.",
          "Pensa ai piedi: metti la punta, non il tallone.",
          "Respira in modo regolare per tutta la traversata.",
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
  {
    id: "main",
    label: "Blocco Principale — 4×4 Bouldering",
    moduleRole: "main_set",
    durationLabel: "~20 min",
    exercises: [
      {
        card: {
          exercise_id: "four_by_four",
          name: "4×4 Boulder",
          sets: 4,
          reps: "4 problemi",
          rest_s: 240,
          notes: "Scegli 4 boulder a flash–1 (1–2 gradi sotto il tuo flash). Scala tutti e 4 senza riposo, poi riposa 4 min.",
        },
        cues: [
          "Scegli 4 problemi che riesci a flashare o quasi.",
          "Scala tutti e 4 consecutivamente senza fermarti.",
          "Non preoccuparti se cadi — continua al problema successivo.",
          "4 minuti di riposo tra ogni round: siediti, respira, recupera.",
          "Obiettivo: mantenere la qualità del movimento su tutti e 4 i round.",
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
  {
    id: "strength",
    label: "Forza dita — Hangboard",
    moduleRole: "main_set",
    durationLabel: "~10 min",
    exercises: [
      {
        card: {
          exercise_id: "hangboard_repeaters",
          name: "Repeaters su hangboard",
          sets: 3,
          reps: "6 rip × 7s on / 3s off",
          rest_s: 120,
          notes: "Half crimp. Usa la presa più grande su cui senti tensione ma non dolore.",
        },
        cues: [
          "Half crimp: dita a 90° nella seconda falange — mai full crimp se sei stanco.",
          "7 secondi di hang, 3 secondi di riposo (lascia la presa ma tieniti vicino).",
          "6 ripetizioni = 1 serie. Poi riposa 2 minuti.",
          "Se devi usare un elastico per ridurre il carico, usalo — è allenamento vero.",
          "Sensazione target: tensione nelle dita, mai dolore articolare.",
          "Se senti dolore alle pulegge, fermati subito.",
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
  {
    id: "cooldown",
    label: "Defaticamento",
    moduleRole: "cooldown",
    durationLabel: "~5 min",
    exercises: [
      {
        card: {
          exercise_id: "forearm_stretch",
          name: "Stretch avambracci",
          sets: 2,
          reps: "30s",
          notes: "Braccio teso, palmo verso il basso. Piega il polso con l'altra mano.",
        },
        cues: [
          "Braccio teso davanti a te, palmo verso il basso.",
          "Con l'altra mano, abbassa piano il dorso della mano verso il pavimento.",
          "Tieni 30 secondi, respira. Poi cambia braccio.",
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
          name: "Stretch spalle",
          sets: 2,
          reps: "30s",
          notes: "Porta il braccio attraverso il petto, tieni con il braccio opposto.",
        },
        cues: [
          "Porta il braccio sinistro attraverso il petto a 90°.",
          "Con il braccio destro, premi delicatamente il gomito verso il petto.",
          "30 secondi, poi cambia lato.",
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
          name: "Respirazione profonda",
          sets: 1,
          reps: "1 min",
          notes: "Inhala 4s, tieni 4s, esala 6s. Chiudi gli occhi.",
        },
        cues: [
          "Siediti o sdraiati comodamente.",
          "Inhala dal naso per 4 secondi.",
          "Tieni per 4 secondi.",
          "Esala lentamente dalla bocca per 6 secondi.",
          "Ripeti per 1 minuto. La sessione è finita — ottimo lavoro.",
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
      Il tuo piano personalizzato è diverso da questo — calibrato su di te.
    </p>
    <p className="text-xs text-muted-foreground">
      Gradi, obiettivi, disponibilità settimanale, palestre. Tutto calcolato in 5 minuti.
    </p>
    <Link href="/onboarding/welcome">
      <Button size="sm" className="gap-2">
        Crea il tuo piano gratuito
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
            {cuesOpen ? "Nascondi cues" : "Mostra cues"}
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
            {timerOpen ? "Chiudi timer" : "Usa timer"}
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
      {/* Hero */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-3">
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-bold text-amber-400 tracking-wide uppercase">
              Demo
            </span>
            <span className="text-sm font-medium text-foreground">Sessione palestra</span>
          </div>
          <span className="text-xs text-muted-foreground">~45 min</span>
        </div>
      </div>

      {/* Intro banner */}
      <div className="mx-auto max-w-3xl px-4 pt-5 pb-2">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-1.5">
          <p className="text-sm font-semibold text-amber-400">
            Questa è una sessione di esempio per scalatori 6b–7a
          </p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Il tuo piano reale sarà diverso: calibrato sui tuoi gradi, obiettivi, palestre
            disponibili e giorni liberi. Questa demo mostra l&apos;esperienza che avrai ogni sessione.
          </p>
        </div>
      </div>

      {/* Session blocks */}
      <div className="mx-auto max-w-3xl px-4 space-y-8 mt-6">
        {DEMO_BLOCKS.map((block) => (
          <BlockSection
            key={block.id}
            block={block}
            showCtaAfter={block.id === "strength"}
          />
        ))}

        {/* Divider + final message */}
        <div className="text-center space-y-2 pt-4 pb-2">
          <p className="text-sm font-medium text-foreground">Sessione completata. Ottimo lavoro!</p>
          <p className="text-xs text-muted-foreground">
            Ogni sessione del tuo piano reale include feedback, adattamento automatico e progressione settimana per settimana.
          </p>
        </div>
      </div>

      {/* Sticky CTA bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <div className="mx-auto max-w-3xl flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground leading-snug">
            Vuoi un piano personalizzato su di te?
          </p>
          <Link href="/onboarding/welcome" className="shrink-0">
            <Button size="sm" className="gap-1.5">
              Inizia gratis
              <ArrowRight className="size-3.5" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
