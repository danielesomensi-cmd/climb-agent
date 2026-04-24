import { notFound } from "next/navigation";

export const dynamic = "force-static";

type Swatch = {
  name: string;
  hsl: string;
  utility: string;
};

const SURFACES: Swatch[] = [
  { name: "surface-base", hsl: "222 28% 8%", utility: "bg-surface-base" },
  { name: "surface-raised", hsl: "222 25% 12%", utility: "bg-surface-raised" },
  { name: "surface-elevated", hsl: "222 22% 16%", utility: "bg-surface-elevated" },
  { name: "surface-inset", hsl: "222 30% 6%", utility: "bg-surface-inset" },
];

const FOREGROUNDS: Swatch[] = [
  { name: "fg", hsl: "210 20% 98%", utility: "text-fg" },
  { name: "fg-secondary", hsl: "215 15% 75%", utility: "text-fg-secondary" },
  { name: "fg-muted", hsl: "215 12% 55%", utility: "text-fg-muted" },
  { name: "fg-disabled", hsl: "215 10% 35%", utility: "text-fg-disabled" },
];

const BORDERS: Swatch[] = [
  { name: "border-subtle", hsl: "222 20% 18%", utility: "border-border-subtle" },
  { name: "border-default", hsl: "222 18% 25%", utility: "border-border-default" },
  { name: "border-strong", hsl: "222 15% 40%", utility: "border-border-strong" },
];

type Functional = Swatch & {
  mutedBg: string;
  mutedFg: string;
};

const FUNCTIONAL: Functional[] = [
  {
    name: "success",
    hsl: "145 65% 48%",
    utility: "bg-success",
    mutedBg: "bg-success-muted",
    mutedFg: "text-success",
  },
  {
    name: "warning",
    hsl: "40 90% 55%",
    utility: "bg-warning",
    mutedBg: "bg-warning-muted",
    mutedFg: "text-warning",
  },
  {
    name: "danger",
    hsl: "0 75% 58%",
    utility: "bg-danger",
    mutedBg: "bg-danger-muted",
    mutedFg: "text-danger",
  },
  {
    name: "info",
    hsl: "210 85% 60%",
    utility: "bg-info",
    mutedBg: "bg-info-muted",
    mutedFg: "text-info",
  },
];

const AXES: Swatch[] = [
  { name: "finger", hsl: "285 75% 60%", utility: "bg-axis-finger" },
  { name: "pulling", hsl: "220 80% 62%", utility: "bg-axis-pulling" },
  { name: "power-endurance", hsl: "25 90% 58%", utility: "bg-axis-power-endurance" },
  { name: "endurance", hsl: "160 70% 50%", utility: "bg-axis-endurance" },
  { name: "technique", hsl: "190 85% 55%", utility: "bg-axis-technique" },
];

const PHASES: Swatch[] = [
  { name: "aerobic", hsl: "195 70% 55%", utility: "bg-phase-aerobic" },
  { name: "anaerobic-alactic", hsl: "340 80% 60%", utility: "bg-phase-anaerobic-alactic" },
  { name: "anaerobic-lactic", hsl: "25 90% 58%", utility: "bg-phase-anaerobic-lactic" },
  { name: "specific", hsl: "285 75% 60%", utility: "bg-phase-specific" },
  { name: "recovery", hsl: "145 55% 55%", utility: "bg-phase-recovery" },
];

const RADII = [
  { name: "sm", value: "6px", utility: "rounded-sm" },
  { name: "md", value: "10px", utility: "rounded-md" },
  { name: "lg", value: "16px", utility: "rounded-lg" },
  { name: "xl", value: "24px", utility: "rounded-xl" },
  { name: "pill", value: "999px", utility: "rounded-pill" },
];

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-xl font-semibold text-fg">{title}</h2>
        {subtitle ? (
          <p className="mt-1 text-sm text-fg-muted">{subtitle}</p>
        ) : null}
      </header>
      <div>{children}</div>
    </section>
  );
}

function TokenLabel({ swatch }: { swatch: Swatch }) {
  return (
    <div className="space-y-0.5 font-mono text-xs">
      <div className="text-fg">{swatch.name}</div>
      <div className="text-fg-muted">{swatch.hsl}</div>
      <div className="text-fg-muted">{swatch.utility}</div>
    </div>
  );
}

export default function TokensPage() {
  if (process.env.NODE_ENV === "production") notFound();
  if (process.env.VERCEL_ENV === "preview") notFound();

  return (
    <div className="min-h-screen bg-surface-base p-6 md:p-10">
      <div className="mx-auto max-w-5xl space-y-12">
        <header className="space-y-2 border-b border-border-subtle pb-6">
          <p className="font-mono text-xs uppercase tracking-widest text-brand">
            A214 · /dev/tokens
          </p>
          <h1 className="text-3xl font-semibold text-fg">Dark Performance tokens</h1>
          <p className="text-sm text-fg-secondary">
            Foundation preview. Dev/localhost only; 404 on prod + preview.
          </p>
        </header>

        <Section
          title="1. Surfaces"
          subtitle="Page background, card surface, popover/modal, recessed input"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {SURFACES.map((s) => (
              <div
                key={s.name}
                className="space-y-3 rounded-lg border border-border-subtle p-4"
                style={{ backgroundColor: `hsl(${s.hsl})` }}
              >
                <div className="h-20 rounded-md border border-border-subtle" />
                <TokenLabel swatch={s} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="2. Foregrounds"
          subtitle="Text samples rendered on bg-surface-raised"
        >
          <div className="space-y-2 rounded-lg border border-border-default bg-surface-raised p-6">
            {FOREGROUNDS.map((s) => (
              <div key={s.name} className="flex items-baseline gap-4">
                <span className={`text-base ${s.utility}`}>
                  The quick brown fox jumps over the lazy dog.
                </span>
                <span className="ml-auto">
                  <TokenLabel swatch={s} />
                </span>
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="3. Borders"
          subtitle="Border weights at 1px, on surface-raised"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {BORDERS.map((s) => (
              <div
                key={s.name}
                className={`space-y-3 rounded-lg border bg-surface-raised p-4 ${s.utility}`}
              >
                <div className="h-16 rounded-md bg-surface-elevated" />
                <TokenLabel swatch={s} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="4. Brand + accents"
          subtitle="CTAs use shadcn bg-primary (alias to --accent-primary). New bg-brand utilities for scoped highlights."
        >
          <div className="space-y-4 rounded-lg border border-border-default bg-surface-raised p-6">
            <div className="flex flex-wrap gap-3">
              <button className="rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-brand-hover">
                bg-primary (CTA)
              </button>
              <button className="rounded-md bg-brand-muted px-4 py-2 font-medium text-brand hover:bg-brand-muted/70">
                bg-brand-muted
              </button>
              <button className="rounded-md border border-border-default px-4 py-2 font-medium text-fg hover:bg-accent">
                Ghost (shadcn)
              </button>
            </div>
            <div className="flex flex-wrap gap-3">
              <button className="rounded-md bg-brand-secondary px-4 py-2 font-medium text-brand-secondary-fg">
                bg-brand-secondary
              </button>
              <button className="rounded-md bg-brand-secondary-muted px-4 py-2 font-medium text-brand-secondary">
                bg-brand-secondary-muted
              </button>
            </div>
            <p className="font-mono text-xs text-fg-muted">
              Rule: CTAs use bg-primary. `bg-brand` namespace for scoped brand fills
              (badges, highlighted cards). `bg-accent` is reserved for shadcn ghost
              hover — do not override.
            </p>
          </div>
        </Section>

        <Section
          title="5. Functional badges"
          subtitle="success / warning / danger / info (+ their -muted variants)"
        >
          <div className="flex flex-wrap gap-3">
            {FUNCTIONAL.map((s) => (
              <div
                key={s.name}
                className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-4"
              >
                <div className="flex gap-2">
                  <span
                    className={`rounded-pill px-3 py-1 text-xs font-semibold text-fg ${s.utility}`}
                  >
                    {s.name}
                  </span>
                  <span
                    className={`rounded-pill border border-border-subtle px-3 py-1 text-xs font-semibold ${s.mutedBg} ${s.mutedFg}`}
                  >
                    {s.name}-muted
                  </span>
                </div>
                <TokenLabel swatch={s} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="6. Training axes (5)"
          subtitle="Assessment radar colors: finger / pulling / power-endurance / endurance / technique"
        >
          <div className="flex flex-wrap gap-3">
            {AXES.map((s) => (
              <div
                key={s.name}
                className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-3"
              >
                <span
                  className={`inline-block rounded-pill px-3 py-1 text-xs font-semibold text-fg ${s.utility}`}
                >
                  {s.name}
                </span>
                <TokenLabel swatch={s} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="7. Phase colors (5)"
          subtitle="Macrocycle timeline: aerobic / anaerobic-alactic / anaerobic-lactic / specific / recovery"
        >
          <div className="flex flex-wrap gap-3">
            {PHASES.map((s) => (
              <div
                key={s.name}
                className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-3"
              >
                <span
                  className={`inline-block rounded-pill px-3 py-1 text-xs font-semibold text-fg ${s.utility}`}
                >
                  {s.name}
                </span>
                <TokenLabel swatch={s} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="8. Glow"
          subtitle="Used sparingly — primary CTA rings, highlighted cards only"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2 rounded-lg border border-border-default bg-surface-raised p-6 shadow-glow-primary">
              <div className="font-semibold text-fg">shadow-glow-primary</div>
              <p className="font-mono text-xs text-fg-muted">
                0 0 24px -4px hsl(340 85% 58% / 0.35)
              </p>
            </div>
            <div className="space-y-2 rounded-lg border border-border-default bg-surface-raised p-6 shadow-glow-secondary">
              <div className="font-semibold text-fg">shadow-glow-secondary</div>
              <p className="font-mono text-xs text-fg-muted">
                0 0 24px -4px hsl(190 90% 55% / 0.35)
              </p>
            </div>
          </div>
        </Section>

        <Section
          title="9. Shadow scale"
          subtitle="sm (hairline lift) / md (card elevation) / lg (drawer, modal)"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-6 shadow-sm">
              <div className="font-semibold text-fg">shadow-sm</div>
              <p className="font-mono text-xs text-fg-muted">
                0 1px 2px 0 hsl(222 40% 2% / 0.40)
              </p>
            </div>
            <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-6 shadow-md">
              <div className="font-semibold text-fg">shadow-md</div>
              <p className="font-mono text-xs text-fg-muted">
                0 4px 12px -2px hsl(222 40% 2% / 0.50)
              </p>
            </div>
            <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised p-6 shadow-lg">
              <div className="font-semibold text-fg">shadow-lg</div>
              <p className="font-mono text-xs text-fg-muted">
                0 12px 32px -8px hsl(222 40% 2% / 0.60)
              </p>
            </div>
          </div>
        </Section>

        <Section
          title="10. Radius"
          subtitle="sm / md / lg / xl / pill — flat values (no calc cascade)"
        >
          <div className="flex flex-wrap items-end gap-4">
            {RADII.map((r) => (
              <div key={r.name} className="space-y-2 text-center">
                <div
                  className={`h-20 w-20 border border-border-default bg-surface-elevated ${r.utility}`}
                />
                <div className="font-mono text-xs">
                  <div className="text-fg">{r.name}</div>
                  <div className="text-fg-muted">{r.value}</div>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <footer className="border-t border-border-subtle pt-6 font-mono text-xs text-fg-muted">
          Source: <code className="text-fg">frontend/src/app/globals.css</code>
          {" · "}
          Doc:{" "}
          <code className="text-fg">docs/design_system_v1.md</code>
        </footer>
      </div>
    </div>
  );
}
