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
import { Check, Mountain } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/hooks/use-media-query";
import { getOutdoorSpots, addOutdoorSpot } from "@/lib/api";
import type { OutdoorSpot } from "@/lib/types";
import { formatDateShort } from "@/lib/format";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface ReplanDialogProps {
  open: boolean;
  date: string;
  gyms: Gym[];
  sessionIndex?: number;
  onClose: () => void;
  onApply: (data: {
    intent: string;
    location: string;
    gym_id?: string;
    session_index?: number;
    // B360 — dove si va. Obbligatori sul ramo outdoor (Apply resta disabled
    // finché non scegli): senza, il backend scriveva l'intent come falesia.
    spot_id?: string;
    spot_name?: string;
    // A301 review — "Skip day" replaces every engine session of the day (the
    // user's own sessions and the done ones stay).
    whole_day?: boolean;
  }) => void;
}

const INDOOR_INTENT_OPTIONS = [
  { value: "rest", label: "Rest", description: "Full rest day" },
  { value: "recovery", label: "Easy", description: "Light recovery or yoga" },
  { value: "projecting", label: "Projecting", description: "Try your project route/boulder" },
  { value: "strength", label: "Strength", description: "Max hangs, limit bouldering" },
  { value: "endurance", label: "Endurance", description: "ARC, long routes, volume" },
  { value: "power_endurance", label: "Power Endurance", description: "4x4, intervals" },
  { value: "technique", label: "Technique", description: "Drills and movement quality" },
  { value: "hard", label: "Hard", description: "Full intensity session (auto-select)" },
];

const OUTDOOR_INTENT_OPTIONS = [
  { value: "outdoor_easy", label: "Easy outdoor", description: "Easy climbing, warm-up routes" },
  { value: "outdoor_projecting", label: "Projecting", description: "Work your project" },
  { value: "outdoor_volume", label: "Volume routes", description: "Many routes, endurance focus" },
  { value: "outdoor_boulder", label: "Boulder outdoor", description: "Outdoor bouldering session" },
];

/** A308 — location / discipline chips: 44px targets, same look everywhere. */
function chipClass(selected: boolean): string {
  return cn(
    "min-h-11 rounded-md border px-4 text-sm transition-colors",
    selected
      ? "border-primary bg-primary/10 text-primary font-medium"
      : "border-muted text-muted-foreground hover:border-primary/40",
  );
}

export function ReplanDialog({
  open,
  date,
  gyms,
  sessionIndex,
  onClose,
  onApply,
}: ReplanDialogProps) {
  const [location, setLocation] = useState<string>("gym");
  const [intent, setIntent] = useState<string>("rest");
  // B360 — picker falesia (stesso blocco di quick-add-dialog.tsx)
  const [spots, setSpots] = useState<OutdoorSpot[]>([]);
  const [selectedSpot, setSelectedSpot] = useState<OutdoorSpot | null>(null);
  const [addingSpot, setAddingSpot] = useState(false);
  const [newSpotName, setNewSpotName] = useState("");
  const [newSpotDiscipline, setNewSpotDiscipline] = useState<"lead" | "boulder" | "both">("lead");

  const isOutdoor = location === "outdoor";
  const intentOptions = isOutdoor ? OUTDOOR_INTENT_OPTIONS : INDOOR_INTENT_OPTIONS;

  // B360 — carica gli spot quando si passa su outdoor
  useEffect(() => {
    if (!open || !isOutdoor) return;
    getOutdoorSpots()
      .then((data) => setSpots(data.spots))
      .catch(() => setSpots([]));
  }, [open, isOutdoor]);

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
      setAddingSpot(false);
      setNewSpotName("");
    } catch {
      // silently fail — user can retry
    }
  };

  const handleApply = () => {
    let resolvedIntent = intent;
    // For strength/hard + home, use finger_max (most common home hard session)
    if ((intent === "strength" || intent === "hard") && location === "home") {
      resolvedIntent = "finger_max";
    }
    if (isOutdoor) {
      // B360 — senza falesia non si applica (bottone disabled): il nome della
      // falesia non può più essere dedotto dall'intent.
      if (!selectedSpot) return;
      onApply({
        intent: resolvedIntent,
        location: "outdoor",
        session_index: sessionIndex,
        spot_id: selectedSpot.id,
        spot_name: selectedSpot.name,
      });
      return;
    }
    const isGym = location !== "home";
    onApply({
      intent: resolvedIntent,
      location: isGym ? "gym" : "home",
      gym_id: isGym ? location : undefined,
      session_index: sessionIndex,
    });
  };

  const handleSkip = () => {
    onApply({ intent: "rest", location: "home", whole_day: true });
  };

  // A308 — on a phone the same content opens as a bottom sheet (the week
  // picker's pattern): the actions sit under the thumb, not mid-screen.
  const isSmall = useMediaQuery("(max-width: 639px)");
  const title = `Change plan — ${formatDateShort(date)}`;

  const body = (
    <div className="space-y-4 py-2 overflow-y-auto min-h-0 flex-1">
      {/* Location */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Location</Label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={chipClass(location === "home")}
            onClick={() => setLocation("home")}
          >
            Home
          </button>
          {gyms.length > 0
            ? gyms.map((g, i) => {
                const id = g.gym_id || `gym-${i}`;
                return (
                  <button
                    key={i}
                    type="button"
                    className={chipClass(location === id)}
                    onClick={() => setLocation(id)}
                  >
                    {g.name || `Gym ${i + 1}`}
                  </button>
                );
              })
            : (
                <button
                  type="button"
                  className={chipClass(location === "gym")}
                  onClick={() => setLocation("gym")}
                >
                  Gym
                </button>
              )}
          <button
            type="button"
            className={chipClass(location === "outdoor")}
            onClick={() => {
              setLocation("outdoor");
              setIntent("outdoor_easy");
            }}
          >
            Outdoor
          </button>
        </div>
      </div>

      {/* B360 — Spot picker: obbligatorio sul ramo outdoor */}
      {isOutdoor && (
        <div className="space-y-2">
          <Label className="text-sm font-medium">Where?</Label>
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
                  onClick={() => setSelectedSpot(spot)}
                >
                  <div className="flex items-center gap-2">
                    <Mountain className="size-3.5 text-success" />
                    <span className="font-medium">{spot.name}</span>
                    <Badge variant="outline" className="text-[10px] ml-auto">{spot.discipline}</Badge>
                  </div>
                </button>
              ))}
            </div>
          ) : !addingSpot ? (
            <p className="text-xs text-muted-foreground italic">No saved spots</p>
          ) : null}

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
                    className={chipClass(newSpotDiscipline === d)}
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
      )}

      {/* Intent */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">What do you want to do?</Label>
        <div className="space-y-1.5">
          {intentOptions.map((opt) => (
            <button
              key={opt.value}
              type="button"
              aria-pressed={intent === opt.value}
              className={cn(
                "flex min-h-14 w-full items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors",
                intent === opt.value
                  ? "border-primary bg-primary/10"
                  : "border-muted hover:border-primary/40",
              )}
              onClick={() => setIntent(opt.value)}
            >
              {/* A308 — radio-style mark: the choice no longer rests on a border tint. */}
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full border",
                  intent === opt.value ? "border-primary bg-primary text-primary-foreground" : "border-border-strong",
                )}
                aria-hidden="true"
              >
                {intent === opt.value && <Check className="size-3" />}
              </span>
              <span className="min-w-0">
                <span className={cn("block text-sm font-medium", intent === opt.value ? "text-primary" : "text-fg")}>
                  {opt.label}
                </span>
                <span className="block text-xs text-muted-foreground">{opt.description}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  const actions = (
    <>
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
      {/* B360 — stesso vincolo di quick-add: outdoor senza falesia non parte */}
      <Button size="sm" onClick={handleApply} disabled={isOutdoor && !selectedSpot}>
        Apply
      </Button>
    </>
  );

  if (isSmall) {
    return (
      <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
        <DrawerContent className="max-h-[90dvh]">
          <DrawerHeader className="text-left">
            <DrawerTitle>{title}</DrawerTitle>
          </DrawerHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4">{body}</div>
          <DrawerFooter className="pb-[calc(1rem+env(safe-area-inset-bottom,0px))]">{actions}</DrawerFooter>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md max-h-[75dvh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        {body}

        <DialogFooter className="flex-col gap-2 sm:flex-row shrink-0 pb-[env(safe-area-inset-bottom,0px)]">
          {actions}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
