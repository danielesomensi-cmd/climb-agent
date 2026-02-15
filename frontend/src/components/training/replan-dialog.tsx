"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface Gym {
  name: string;
  equipment: string[];
}

interface ReplanDialogProps {
  open: boolean;
  date: string;
  gyms: Gym[];
  onClose: () => void;
  onApply: (data: { intent: string; location: string; gym_id?: string }) => void;
}

const INTENSITY_OPTIONS = [
  { value: "rest", label: "Rest", description: "Full rest day" },
  { value: "recovery", label: "Easy", description: "Light recovery or yoga" },
  { value: "strength", label: "Hard", description: "Full intensity session" },
];

/** Format date as "15 Feb" */
function formatDateLabel(dateStr: string): string {
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const day = parseInt(parts[2], 10);
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${day} ${months[monthIdx] ?? parts[1]}`;
}

export function ReplanDialog({
  open,
  date,
  gyms,
  onClose,
  onApply,
}: ReplanDialogProps) {
  const [location, setLocation] = useState<string>("gym");
  const [intensity, setIntensity] = useState<string>("rest");

  const handleApply = () => {
    let intent = intensity;
    // For hard + home, use finger_max (most common home hard session)
    if (intensity === "strength" && location === "home") {
      intent = "finger_max";
    }
    const isGym = location !== "home";
    onApply({
      intent,
      location: isGym ? "gym" : "home",
      gym_id: isGym ? location : undefined,
    });
  };

  const handleSkip = () => {
    onApply({ intent: "rest", location: "home" });
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Change plan — {formatDateLabel(date)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Location */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Location</Label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                  location === "home"
                    ? "border-primary bg-primary/10 text-primary font-medium"
                    : "border-muted text-muted-foreground hover:border-primary/40"
                }`}
                onClick={() => setLocation("home")}
              >
                Home
              </button>
              {gyms.length > 0
                ? gyms.map((g, i) => {
                    const id = g.name || `gym-${i}`;
                    return (
                      <button
                        key={i}
                        type="button"
                        className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                          location === id
                            ? "border-primary bg-primary/10 text-primary font-medium"
                            : "border-muted text-muted-foreground hover:border-primary/40"
                        }`}
                        onClick={() => setLocation(id)}
                      >
                        {g.name || `Gym ${i + 1}`}
                      </button>
                    );
                  })
                : (
                    <button
                      type="button"
                      className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                        location === "gym"
                          ? "border-primary bg-primary/10 text-primary font-medium"
                          : "border-muted text-muted-foreground hover:border-primary/40"
                      }`}
                      onClick={() => setLocation("gym")}
                    >
                      Gym
                    </button>
                  )}
            </div>
          </div>

          {/* Intensity */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Intensity</Label>
            <div className="space-y-1.5">
              {INTENSITY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                    intensity === opt.value
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-muted text-muted-foreground hover:border-primary/40"
                  }`}
                  onClick={() => setIntensity(opt.value)}
                >
                  <span className="font-medium">{opt.label}</span>
                  <span className="text-muted-foreground"> — {opt.description}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button
            variant="destructive"
            size="sm"
            onClick={handleSkip}
            className="sm:mr-auto"
          >
            Skip day
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleApply}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
