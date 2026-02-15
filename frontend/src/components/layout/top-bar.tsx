"use client";

import { DarkModeToggle } from "./dark-mode-toggle";

interface TopBarProps {
  title: string;
  subtitle?: string;
  backHref?: string;
}

export function TopBar({ title, subtitle, backHref }: TopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          {backHref && (
            <a href={backHref} className="min-h-[44px] min-w-[44px] flex items-center justify-center">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </a>
          )}
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
        <DarkModeToggle />
      </div>
    </header>
  );
}
