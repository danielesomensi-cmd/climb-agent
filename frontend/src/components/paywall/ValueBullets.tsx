import { BrainCircuit, RefreshCcw, Mountain } from "lucide-react";

type Bullet = {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
};

const BULLETS: Bullet[] = [
  {
    icon: BrainCircuit,
    title: "AI-driven periodization",
    body: "Your plan adapts from every session you log, following proven Hörst / Lattice frameworks.",
  },
  {
    icon: RefreshCcw,
    title: "Every week, smarter",
    body: "Feedback from 5 performance axes reshapes your next block automatically.",
  },
  {
    icon: Mountain,
    title: "Built for lead & boulder",
    body: "Fontainebleau grades, finger / power / endurance phases, no generic fitness noise.",
  },
];

export function ValueBullets() {
  return (
    <section className="px-6 py-8 space-y-5">
      {BULLETS.map(({ icon: Icon, title, body }) => (
        <div key={title} className="flex items-start gap-4">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-muted text-brand">
            <Icon className="size-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-fg">{title}</h3>
            <p className="mt-1 text-sm text-fg-secondary">{body}</p>
          </div>
        </div>
      ))}
    </section>
  );
}
