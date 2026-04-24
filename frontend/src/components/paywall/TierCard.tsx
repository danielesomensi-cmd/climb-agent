import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";

type TierVariant = "founding" | "standard";

export type TierCardProps = {
  variant: TierVariant;
  price: string;
  priceInterval: string;
  badge?: string;
  tagline: string;
  bullets: string[];
  ctaLabel: string;
  loading?: boolean;
  disabled?: boolean;
  onCtaClick: () => void;
};

export function TierCard({
  variant,
  price,
  priceInterval,
  badge,
  tagline,
  bullets,
  ctaLabel,
  loading = false,
  disabled = false,
  onCtaClick,
}: TierCardProps) {
  const isFounding = variant === "founding";

  const shellClasses = isFounding
    ? "relative rounded-xl border border-brand bg-surface-elevated shadow-glow-primary p-6"
    : "relative rounded-xl border border-border-subtle bg-surface-raised p-6";

  return (
    <article className={shellClasses}>
      {badge && isFounding && (
        <div className="mb-3 inline-flex items-center rounded-pill bg-brand-muted px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand">
          {badge}
        </div>
      )}

      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-fg">
          {isFounding ? "Founding Climber" : "Standard"}
        </h2>
        <p className="text-sm text-fg-secondary">{tagline}</p>
      </header>

      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-4xl font-bold text-fg">{price}</span>
        <span className="text-sm text-fg-muted">{priceInterval}</span>
      </div>

      <ul className="mt-5 space-y-2.5">
        {bullets.map((b) => (
          <li key={b} className="flex items-start gap-2 text-sm text-fg-secondary">
            <Check
              className={`mt-0.5 size-4 shrink-0 ${
                isFounding ? "text-brand" : "text-success"
              }`}
              aria-hidden="true"
            />
            <span>{b}</span>
          </li>
        ))}
      </ul>

      <Button
        className="mt-6 w-full"
        size="lg"
        variant={isFounding ? "default" : "outline"}
        onClick={onCtaClick}
        disabled={disabled || loading}
      >
        {loading ? "Loading..." : ctaLabel}
      </Button>
    </article>
  );
}
