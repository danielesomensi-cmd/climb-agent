"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getSuggestedSessions, getSessions } from "@/lib/api";
import type { SessionMeta } from "@/lib/types";

interface Gym {
  name: string;
  equipment: string[];
}

interface QuickAddDialogProps {
  open: boolean;
  date: string;
  gyms: Gym[];
  onClose: () => void;
  onApply: (data: {
    session_id: string;
    slot: string;
    location: string;
    gym_id?: string;
  }) => void;
}

const SLOT_OPTIONS = [
  { value: "morning", label: "Morning" },
  { value: "lunch", label: "Lunch" },
  { value: "evening", label: "Evening" },
];

const INTENSITY_COLORS: Record<string, string> = {
  low: "bg-green-500/20 text-green-400 border-green-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  max: "bg-red-500/20 text-red-400 border-red-500/30",
};

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

export function QuickAddDialog({
  open,
  date,
  gyms,
  onClose,
  onApply,
}: QuickAddDialogProps) {
  const [slot, setSlot] = useState("evening");
  const [location, setLocation] = useState<string>("gym");
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<
    Array<{ session_id: string; intensity: string; estimated_load_score: number; reason: string }>
  >([]);
  const [allSessions, setAllSessions] = useState<SessionMeta[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Reset state when dialog opens/closes or date changes
  useEffect(() => {
    if (open) {
      setSlot("evening");
      setLocation("gym");
      setSelectedSession(null);
      setSuggestions([]);
      setAllSessions(null);
      setShowAll(false);
      setWarning(null);
    }
  }, [open, date]);

  // Fetch suggestions when dialog opens or location changes
  useEffect(() => {
    if (!open || !date) return;
    setLoading(true);
    const resolvedLocation = location === "home" ? "home" : "gym";
    getSuggestedSessions(date, resolvedLocation)
      .then((data) => {
        setSuggestions(data.suggestions);
        setSelectedSession(null);
      })
      .catch(() => setSuggestions([]))
      .finally(() => setLoading(false));
  }, [open, date, location]);

  const handleBrowseAll = async () => {
    if (allSessions) {
      setShowAll(!showAll);
      return;
    }
    try {
      const data = await getSessions();
      setAllSessions(data.sessions);
      setShowAll(true);
    } catch {
      setAllSessions([]);
      setShowAll(true);
    }
  };

  const handleApply = () => {
    if (!selectedSession) return;
    const isGym = location !== "home";
    onApply({
      session_id: selectedSession,
      slot,
      location: isGym ? "gym" : "home",
      gym_id: isGym && location !== "gym" ? location : undefined,
    });
  };

  const resolvedLocation = location === "home" ? "home" : "gym";

  // Filter all sessions by location
  const filteredAll = allSessions?.filter((s) => {
    const loc = s.location?.toLowerCase() ?? "";
    if (resolvedLocation === "home") return loc.includes("home") || loc.includes("both");
    return loc.includes("gym") || loc.includes("both");
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add session — {formatDateLabel(date)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Slot picker */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Time slot</Label>
            <div className="flex gap-2">
              {SLOT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`flex-1 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                    slot === opt.value
                      ? "border-primary bg-primary/10 text-primary font-medium"
                      : "border-muted text-muted-foreground hover:border-primary/40"
                  }`}
                  onClick={() => setSlot(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Location picker */}
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

          {/* Suggestions */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Suggested sessions</Label>
            {loading ? (
              <div className="flex justify-center py-4">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : suggestions.length > 0 ? (
              <div className="space-y-1.5">
                {suggestions.map((s) => (
                  <button
                    key={s.session_id}
                    type="button"
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                      selectedSession === s.session_id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-muted text-muted-foreground hover:border-primary/40"
                    }`}
                    onClick={() => setSelectedSession(s.session_id)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">
                        {s.session_id.replace(/_/g, " ")}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${INTENSITY_COLORS[s.intensity] ?? ""}`}
                      >
                        {s.intensity}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {s.reason}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic py-2">
                No suggestions available
              </p>
            )}
          </div>

          {/* Browse all */}
          <button
            type="button"
            className="text-xs text-primary underline"
            onClick={handleBrowseAll}
          >
            {showAll ? "Hide all sessions" : "Browse all sessions..."}
          </button>

          {showAll && filteredAll && (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {filteredAll.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                    selectedSession === s.id
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-muted text-muted-foreground hover:border-primary/40"
                  }`}
                  onClick={() => setSelectedSession(s.id)}
                >
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted-foreground"> — {s.type}</span>
                </button>
              ))}
              {filteredAll.length === 0 && (
                <p className="text-xs text-muted-foreground italic py-2">
                  No sessions for this location
                </p>
              )}
            </div>
          )}

          {/* Warning */}
          {warning && (
            <div className="rounded-md border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-xs text-orange-400">
              {warning}
            </div>
          )}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleApply}
            disabled={!selectedSession}
          >
            Add Session
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
