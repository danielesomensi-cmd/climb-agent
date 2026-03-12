"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, Home, Mountain, TreePine, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { getWeeklyOverride, putWeeklyOverride, getState } from "@/lib/api";
import type { DayOverviewEntry } from "@/lib/types";

const WEEKDAY_LABELS: Record<string, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

const LOCATION_OPTIONS = [
  { value: "gym", label: "Gym", icon: Mountain },
  { value: "home", label: "Home", icon: Home },
  { value: "outdoor", label: "Outdoor", icon: TreePine },
  { value: "rest", label: "Rest", icon: Calendar },
] as const;

interface EditableDay {
  day: string;
  available: boolean;
  location: string;
  gym_id: string | null;
  is_overridden: boolean;
  modified: boolean;
}

interface Props {
  open: boolean;
  nextWeekStart: string;
  onClose: () => void;
  onPlanUpdated: () => void;
}

export function WeeklyCheckinSheet({ open, nextWeekStart, onClose, onPlanUpdated }: Props) {
  const [days, setDays] = useState<EditableDay[]>([]);
  const [originalDays, setOriginalDays] = useState<DayOverviewEntry[]>([]);
  const [gyms, setGyms] = useState<Array<{ gym_id?: string; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasChanges = days.some((d) => d.modified);

  const fetchData = useCallback(async () => {
    if (!open || !nextWeekStart) return;
    setLoading(true);
    setError(null);
    try {
      const [overrideData, stateData] = await Promise.all([
        getWeeklyOverride(nextWeekStart),
        getState(),
      ]);
      const eq = stateData.equipment as Record<string, unknown> | undefined;
      const gymsList = (eq?.gyms as Array<{ gym_id?: string; name: string }>) ?? [];
      setGyms(gymsList);
      setOriginalDays(overrideData.days);
      setDays(
        overrideData.days.map((d) => ({
          ...d,
          modified: false,
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [open, nextWeekStart]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function updateDay(index: number, updates: Partial<EditableDay>) {
    setDays((prev) =>
      prev.map((d, i) => {
        if (i !== index) return d;
        const updated = { ...d, ...updates };
        // Determine if this differs from the original
        const orig = originalDays[i];
        const isDifferent =
          updated.available !== orig.available ||
          updated.location !== orig.location ||
          updated.gym_id !== orig.gym_id;
        return { ...updated, modified: isDifferent };
      })
    );
  }

  function toggleLocation(index: number, loc: string) {
    const day = days[index];
    if (loc === "rest") {
      updateDay(index, { available: false, location: "rest", gym_id: null });
    } else if (day.location === loc && day.available) {
      // Already selected — no-op (don't toggle off)
      return;
    } else {
      const defaultGym = loc === "gym" && gyms.length > 0 ? (gyms[0].gym_id ?? null) : null;
      updateDay(index, { available: true, location: loc, gym_id: loc === "gym" ? (day.gym_id || defaultGym) : null });
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      // Only send modified days
      const changedDays: Record<string, { available: boolean; location: string; gym_id?: string | null }> = {};
      for (const day of days) {
        if (!day.modified) continue;
        const longName = Object.entries(WEEKDAY_LABELS).find(([k]) => k === day.day)?.[0];
        // Convert short to long name
        const longNames: Record<string, string> = {
          mon: "monday", tue: "tuesday", wed: "wednesday",
          thu: "thursday", fri: "friday", sat: "saturday", sun: "sunday",
        };
        const key = longNames[day.day] || day.day;
        changedDays[key] = {
          available: day.available,
          location: day.location,
          ...(day.gym_id ? { gym_id: day.gym_id } : {}),
        };
      }
      await putWeeklyOverride(nextWeekStart, changedDays);
      onPlanUpdated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function handleDismiss() {
    onClose();
  }

  return (
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader>
          <DrawerTitle>Plan your week</DrawerTitle>
          <p className="text-sm text-muted-foreground">
            Review and adjust next week&apos;s availability
          </p>
        </DrawerHeader>

        <div className="overflow-y-auto px-4 pb-2">
          {loading && (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <p className="text-sm text-destructive text-center py-4">{error}</p>
          )}

          {!loading && !error && (
            <div className="space-y-2">
              {days.map((day, i) => (
                <div
                  key={day.day}
                  className={`rounded-lg border p-3 ${
                    day.modified
                      ? "border-primary/50 bg-primary/5"
                      : "border-border"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">
                      {WEEKDAY_LABELS[day.day] ?? day.day}
                    </span>
                    {day.modified && (
                      <span className="text-xs text-primary font-medium">Modified</span>
                    )}
                  </div>

                  {/* Location buttons */}
                  <div className="flex gap-1.5">
                    {LOCATION_OPTIONS.map((opt) => {
                      const isActive =
                        opt.value === "rest"
                          ? !day.available
                          : day.available && day.location === opt.value;
                      const Icon = opt.icon;
                      return (
                        <button
                          key={opt.value}
                          onClick={() => toggleLocation(i, opt.value)}
                          className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                            isActive
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground hover:bg-muted/80"
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Gym picker (only when gym selected and multiple gyms) */}
                  {day.available && day.location === "gym" && gyms.length > 1 && (
                    <div className="mt-2">
                      <select
                        value={day.gym_id ?? ""}
                        onChange={(e) =>
                          updateDay(i, { gym_id: e.target.value || null })
                        }
                        className="w-full rounded-md border bg-background px-2 py-1.5 text-xs"
                      >
                        {gyms.map((g) => (
                          <option key={g.gym_id ?? g.name} value={g.gym_id ?? ""}>
                            {g.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <DrawerFooter>
          {hasChanges ? (
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save & update plan"
              )}
            </Button>
          ) : (
            <DrawerClose asChild>
              <Button variant="outline" onClick={handleDismiss}>
                Looks good
              </Button>
            </DrawerClose>
          )}
          {hasChanges && (
            <DrawerClose asChild>
              <Button variant="ghost" size="sm">
                Cancel
              </Button>
            </DrawerClose>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
