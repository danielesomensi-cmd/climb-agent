"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A308 — one shape for the notes on /today (radius, padding, tint). Before,
 * each banner picked its own rounded-lg / rounded-xl / Card radius and padding.
 */
const TONE: Record<"primary" | "success" | "warning" | "info", string> = {
  primary: "border-primary/30 bg-primary/5",
  success: "border-success/30 bg-success/10",
  warning: "border-warning/30 bg-warning/10",
  info: "border-info/30 bg-info/5",
};

export function Banner({
  tone,
  onDismiss,
  className,
  children,
}: {
  tone: keyof typeof TONE;
  /** Renders a 44px dismiss button in the top-right corner. */
  onDismiss?: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("relative rounded-xl border p-3 text-sm", TONE[tone], onDismiss && "pr-12", className)}>
      {children}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="absolute right-1 top-1 flex size-11 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
