"use client";

import Link from "next/link";

interface TopBarProps {
  title: string;
  subtitle?: string;
  backHref?: string;
}

export function TopBar({ title, subtitle, backHref }: TopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center px-4 py-3">
        <div className="flex items-center gap-3">
          {/* F40 — era un <a> nativo: navigazione con full reload della PWA e
              nessun nome accessibile (solo SVG). */}
          {backHref && (
            <Link
              href={backHref}
              aria-label="Back"
              className="min-h-[44px] min-w-[44px] flex items-center justify-center"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
          )}
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
      </div>
    </header>
  );
}
