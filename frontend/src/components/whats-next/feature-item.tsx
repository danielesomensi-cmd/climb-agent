"use client";

import type { LucideIcon } from "lucide-react";
import { ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface FeatureItemProps {
  icon: LucideIcon;
  label: string;
  voted: boolean;
  onToggle: () => void;
  implemented?: boolean;
}

export function FeatureItem({ icon: Icon, label, voted, onToggle, implemented }: FeatureItemProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
        <div className="min-w-0 space-y-1">
          <span className="text-sm">{label}</span>
          {implemented && (
            <Badge className="flex w-fit items-center gap-1 bg-green-600/15 text-green-400 border border-green-600/30 text-[10px] px-2 py-0.5 font-medium">
              ✅ Implemented — try it out!
            </Badge>
          )}
        </div>
      </div>
      <Button
        variant={voted ? "default" : "outline"}
        size="icon-sm"
        onClick={onToggle}
        aria-label={voted ? `Remove vote for ${label}` : `Vote for ${label}`}
        className={implemented ? "opacity-50" : ""}
      >
        <ThumbsUp className="h-4 w-4" />
      </Button>
    </div>
  );
}
