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
import { Mountain, ArrowLeft } from "lucide-react";
import { getSuggestedSessions, getSessions, getOutdoorSpots, addOutdoorSpot } from "@/lib/api";
import type { SessionMeta, OutdoorSpot } from "@/lib/types";

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
  onApplyOutdoor?: (data: {
    spot_name: string;
    discipline: string;
    spot_id?: string;
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
  onApplyOutdoor,
}: QuickAddDialogProps) {
  // Indoor state
  const [slot, setSlot] = useState("evening");
  const [location, setLocation] = useState<string>("gym");
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<
    Array<{ session_id: string; session_name?: string; intensity: string; estimated_load_score: number; reason: string; required_equipment?: string[] }>
  >([]);
  const [allSessions, setAllSessions] = useState<SessionMeta[] | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Outdoor state
  const [mode, setMode] = useState<"indoor" | "outdoor">("indoor");
  const [spots, setSpots] = useState<OutdoorSpot[]>([]);
  const [selectedSpot, setSelectedSpot] = useState<OutdoorSpot | null>(null);
  const [outdoorDiscipline, setOutdoorDiscipline] = useState<"lead" | "boulder" | "both">("lead");
  const [addingSpot, setAddingSpot] = useState(false);
  const [newSpotName, setNewSpotName] = useState("");
  const [newSpotDiscipline, setNewSpotDiscipline] = useState<"lead" | "boulder" | "both">("lead");

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
      setMode("indoor");
      setSelectedSpot(null);
      setAddingSpot(false);
      setNewSpotName("");
    }
  }, [open, date]);

  // Fetch suggestions when dialog opens or location changes (indoor only)
  useEffect(() => {
    if (!open || !date || mode !== "indoor") return;
    setLoading(true);
    const resolvedLocation = location === "home" ? "home" : "gym";
    getSuggestedSessions(date, resolvedLocation)
      .then((data) => {
        setSuggestions(data.suggestions);
        setSelectedSession(null);
      })
      .catch(() => setSuggestions([]))
      .finally(() => setLoading(false));
  }, [open, date, location, mode]);

  // Fetch spots when switching to outdoor mode
  useEffect(() => {
    if (mode !== "outdoor") return;
    getOutdoorSpots()
      .then((data) => setSpots(data.spots))
      .catch(() => setSpots([]));
  }, [mode]);

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

  const handleApplyOutdoor = () => {
    if (!selectedSpot || !onApplyOutdoor) return;
    onApplyOutdoor({
      spot_name: selectedSpot.name,
      discipline: outdoorDiscipline,
      spot_id: selectedSpot.id,
    });
  };

  const handleAddSpot = async () => {
    if (!newSpotName.trim()) return;
    try {
      const result = await addOutdoorSpot({
        name: newSpotName.trim(),
        discipline: newSpotDiscipline,
      });
      const spot = result.spot as OutdoorSpot;
      setSpots((prev) => [...prev, spot]);
      setSelectedSpot(spot);
      setOutdoorDiscipline(newSpotDiscipline);
      setAddingSpot(false);
      setNewSpotName("");
    } catch {
      // silently fail — user can retry
    }
  };

  const resolvedLocation = location === "home" ? "home" : "gym";

  // Filter suggestions by equipment compatibility
  const filteredSuggestions = (() => {
    if (location === "home" || location === "gym") return suggestions;
    const gym = gyms.find((g) => g.name === location);
    if (!gym?.equipment) return suggestions;
    return suggestions.filter((s) => {
      const req = s.required_equipment;
      if (!req || req.length === 0) return true;
      return req.every((eq) => gym.equipment.includes(eq));
    });
  })();

  // Equipment available at the selected location
  const selectedGymEquipment: string[] | null = (() => {
    if (location === "home" || location === "gym") return null;
    const gym = gyms.find((g) => g.name === location);
    return gym?.equipment ?? null;
  })();

  // Filter all sessions by location + equipment compatibility
  const filteredAll = allSessions?.filter((s) => {
    const loc = s.location?.toLowerCase() ?? "";
    if (loc !== "any" && loc !== "both") {
      if (resolvedLocation === "home" && !loc.includes("home")) return false;
      if (resolvedLocation === "gym" && !loc.includes("gym")) return false;
    }
    const reqEquip = s.required_equipment;
    if (reqEquip && reqEquip.length > 0 && selectedGymEquipment) {
      return reqEquip.every((eq) => selectedGymEquipment.includes(eq));
    }
    return true;
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add session — {formatDateLabel(date)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Outdoor toggle */}
          {onApplyOutdoor && mode === "indoor" && (
            <button
              type="button"
              className="w-full rounded-lg border border-dashed border-green-500/40 p-3 text-left text-sm transition-colors hover:bg-green-500/5"
              onClick={() => setMode("outdoor")}
            >
              <div className="flex items-center gap-2">
                <Mountain className="size-4 text-green-500" />
                <span className="font-medium">Outdoor session</span>
                <span className="text-xs text-muted-foreground ml-auto">Crag / outdoor</span>
              </div>
            </button>
          )}

          {mode === "outdoor" ? (
            <>
              {/* Back to indoor */}
              <button
                type="button"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => setMode("indoor")}
              >
                <ArrowLeft className="size-3" />
                Back to indoor sessions
              </button>

              {/* Spot picker */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Spot</Label>
                {spots.length > 0 ? (
                  <div className="space-y-1.5">
                    {spots.map((spot) => (
                      <button
                        key={spot.id}
                        type="button"
                        className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                          selectedSpot?.id === spot.id
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-muted text-muted-foreground hover:border-primary/40"
                        }`}
                        onClick={() => {
                          setSelectedSpot(spot);
                          setOutdoorDiscipline(spot.discipline === "both" ? "lead" : spot.discipline);
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <Mountain className="size-3.5 text-green-500" />
                          <span className="font-medium">{spot.name}</span>
                          <Badge variant="outline" className="text-[10px] ml-auto">{spot.discipline}</Badge>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : !addingSpot ? (
                  <p className="text-xs text-muted-foreground italic">No saved spots</p>
                ) : null}

                {/* Add new spot inline */}
                {addingSpot ? (
                  <div className="rounded-lg border border-dashed p-3 space-y-2">
                    <input
                      type="text"
                      placeholder="Spot name (e.g. Berdorf)"
                      value={newSpotName}
                      onChange={(e) => setNewSpotName(e.target.value)}
                      className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                      autoFocus
                    />
                    <div className="flex gap-1.5">
                      {(["lead", "boulder", "both"] as const).map((d) => (
                        <button
                          key={d}
                          type="button"
                          className={`rounded-md border px-3 py-1 text-xs transition-colors ${
                            newSpotDiscipline === d
                              ? "border-primary bg-primary/10 text-primary font-medium"
                              : "border-muted text-muted-foreground"
                          }`}
                          onClick={() => setNewSpotDiscipline(d)}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="text-xs" onClick={() => setAddingSpot(false)}>
                        Cancel
                      </Button>
                      <Button size="sm" className="text-xs" onClick={handleAddSpot} disabled={!newSpotName.trim()}>
                        Save spot
                      </Button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="text-xs text-primary underline"
                    onClick={() => setAddingSpot(true)}
                  >
                    + Add new spot
                  </button>
                )}
              </div>

              {/* Discipline picker */}
              {selectedSpot && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Discipline</Label>
                  <div className="flex gap-2">
                    {(["lead", "boulder", "both"] as const).map((d) => (
                      <button
                        key={d}
                        type="button"
                        className={`flex-1 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                          outdoorDiscipline === d
                            ? "border-primary bg-primary/10 text-primary font-medium"
                            : "border-muted text-muted-foreground hover:border-primary/40"
                        }`}
                        onClick={() => setOutdoorDiscipline(d)}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
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
                ) : filteredSuggestions.length > 0 ? (
                  <div className="space-y-1.5">
                    {filteredSuggestions.map((s) => (
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
                            {s.session_name || s.session_id.replace(/_/g, " ")}
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
                      {s.type && s.type !== "unknown" && (
                        <span className="text-muted-foreground"> — {s.type}</span>
                      )}
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
            </>
          )}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          {mode === "outdoor" ? (
            <Button
              size="sm"
              onClick={handleApplyOutdoor}
              disabled={!selectedSpot}
            >
              Add Outdoor Session
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleApply}
              disabled={!selectedSession}
            >
              Add Session
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
