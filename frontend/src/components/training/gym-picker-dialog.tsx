"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Home, MapPin } from "lucide-react";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface GymPickerDialogProps {
  open: boolean;
  date: string;
  gyms: Gym[];
  onClose: () => void;
  onApply: (data: { gym_id?: string; location: string }) => void;
}

function formatDateShort(dateStr: string): string {
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

export function GymPickerDialog({
  open,
  date,
  gyms,
  onClose,
  onApply,
}: GymPickerDialogProps) {
  const [selected, setSelected] = useState<{
    gym_id?: string;
    location: string;
  } | null>(null);

  function handleApply() {
    if (!selected) return;
    onApply(selected);
    setSelected(null);
  }

  function handleClose() {
    setSelected(null);
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Change location — {formatDateShort(date)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-2">
          {/* Home option */}
          <button
            type="button"
            className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${
              selected?.location === "home"
                ? "border-primary bg-primary/10"
                : "border-border hover:bg-accent"
            }`}
            onClick={() => setSelected({ location: "home" })}
          >
            <div className="flex items-center gap-2">
              <Home className="size-4" />
              <span className="font-medium">Home</span>
            </div>
          </button>

          {/* Gym options */}
          {gyms.map((gym) => (
            <button
              key={gym.name}
              type="button"
              className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${
                selected?.gym_id === (gym.gym_id || gym.name)
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-accent"
              }`}
              onClick={() =>
                setSelected({ gym_id: gym.gym_id || gym.name, location: "gym" })
              }
            >
              <div className="flex items-center gap-2">
                <MapPin className="size-4" />
                <span className="font-medium">{gym.name}</span>
              </div>
            </button>
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleApply} disabled={!selected}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
