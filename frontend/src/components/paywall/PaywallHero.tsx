import Image from "next/image";

/**
 * Flip to `true` once `frontend/public/hero/paywall_hero.webp` exists.
 * Until then, a `HERO_PLACEHOLDER` gray box is rendered at the target
 * dimensions so layout + gradient overlay can be verified.
 */
const HERO_READY = false;

const HERO_SRC = "/hero/paywall_hero.webp";
const HERO_ALT = "Climber on overhanging wall at dusk";

export function PaywallHero() {
  return (
    <section className="relative h-[70vh] w-full overflow-hidden">
      {HERO_READY ? (
        <Image
          src={HERO_SRC}
          alt={HERO_ALT}
          fill
          priority
          sizes="(max-width: 768px) 100vw, 768px"
          className="object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-surface-inset">
          <span className="font-mono text-xs uppercase tracking-widest text-fg-muted">
            HERO_PLACEHOLDER · 1200×800 · 2×
          </span>
        </div>
      )}

      {/* Bottom-up gradient — keeps headline legible on any image */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(to bottom, transparent 40%, hsl(var(--surface-base) / 0.95) 100%)",
        }}
        aria-hidden="true"
      />

      {/* Headline — h2 so TopBar's "Subscribe" stays the page h1 */}
      <div className="absolute inset-x-0 bottom-0 p-6 pb-8">
        <h2 className="text-3xl font-semibold leading-tight tracking-tight text-fg md:text-4xl">
          Train like the top 5% of climbers.
        </h2>
        <p className="mt-2 text-base text-fg-secondary md:text-lg">
          Periodized. Adaptive. Built on science.
        </p>
      </div>
    </section>
  );
}
