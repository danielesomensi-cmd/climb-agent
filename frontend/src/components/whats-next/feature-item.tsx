"use client";

import type { LucideIcon } from "lucide-react";
import { ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FeatureItemProps {
  icon: LucideIcon;
  label: string;
  voted: boolean;
  onToggle: () => void;
}

export function FeatureItem({ icon: Icon, label, voted, onToggle }: FeatureItemProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
        <span className="text-sm">{label}</span>
      </div>
      <Button
        variant={voted ? "default" : "outline"}
        size="icon-sm"
        onClick={onToggle}
        aria-label={voted ? `Remove vote for ${label}` : `Vote for ${label}`}
      >
        <ThumbsUp className="h-4 w-4" />
      </Button>
    </div>
  );
}
