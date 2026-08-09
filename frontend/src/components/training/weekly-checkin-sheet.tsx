"use client";

import { useCallback, useEffect, useState } from "react";
import { Home, Mountain, TreePine, Moon, Loader2, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSubmitLock } from "@/lib/hooks/use-submit-lock";
import {
  Drawer,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { getWeeklyOverride, putWeeklyOverride, getState } from "@/lib/api";
import type { DayOverviewEntry, SlotEntry } from "@/lib/types";

const WEEKDAY_LABELS: Record<string, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

const SLOT_LABELS: Record<string, string> = {
  morning: "Morning",
  lunch: "Lunch",
  evening: "Evening",
};

const LOCATION_OPTIONS = [
  { value: "gym", label: "Gym", icon: Mountain },
  { value: "home", label: "Home", icon: Home },
  { value: "outdoor", label: "Outdoor", icon: TreePine },
] as const;

interface EditableSlot {
  slot: string;
  available: boolean;
  location: string;
  gym_id: string | null;
}

interface EditableDay {
  day: string;
  available: boolean;
  slots: EditableSlot[];
  defaultSlots: EditableSlot[];
  summary: string;
  is_overridden: boolean;
  modified: boolean;
  expanded: boolean;
}

interface Props {
  open: boolean;
  nextWeekStart: string;
  onClose: () => void;
  onPlanUpdated: () => void;
}

function summarizeSlots(slots: EditableSlot[], gyms: Array<{ gym_id?: string; name: string }>): string {
  const gymMap: Record<string, string> = {};
  for (const g of gyms) {
    const id = g.gym_id ?? g.name;
    gymMap[id] = g.name;
  }
  const slotLabels: Record<string, string> = { morning: "AM", lunch: "Lunch", evening: "PM" };
  const parts: string[] = [];
  for (const s of slots) {
    if (!s.available) continue;
    const sl = slotLabels[s.slot] ?? s.slot;
    if (s.location === "gym") {
      const gname = s.gym_id ? (gymMap[s.gym_id] ?? s.gym_id) : "Gym";
      parts.push(`${gname} ${sl}`);
    } else if (s.location === "outdoor") {
      parts.push(`Outdoor ${sl}`);
    } else {
      parts.push(`Home ${sl}`);
    }
  }
  return parts.length > 0 ? parts.join(", ") : "Rest";
}

export function WeeklyCheckinSheet({ open, nextWeekStart, onClose, onPlanUpdated }: Props) {
  const [days, setDays] = useState<EditableDay[]>([]);
  const [originalDays, setOriginalDays] = useState<DayOverviewEntry[]>([]);
  const [gyms, setGyms] = useState<Array<{ gym_id?: string; name: string }>>([]);
  const [loading, setLoading] = useState(false);
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
          day: d.day,
          available: d.available,
          slots: d.slots.map((s) => ({ ...s })),
          defaultSlots: (d.default_slots ?? d.slots).map((s) => ({ ...s })),
          summary: d.summary,
          is_overridden: d.is_overridden,
          modified: false,
          expanded: false,
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

  function isDayModified(day: EditableDay, origIdx: number): boolean {
    const orig = originalDays[origIdx];
    if (!orig) return false;
    if (day.available !== orig.available) return true;
    for (let i = 0; i < day.slots.length; i++) {
      const s = day.slots[i];
      const os = orig.slots[i];
      if (!os) return true;
      if (s.available !== os.available || s.location !== os.location || s.gym_id !== os.gym_id) return true;
    }
    return false;
  }

  function toggleDayRest(index: number) {
    setDays((prev) =>
      prev.map((d, i) => {
        if (i !== index) return d;
        const newAvail = !d.available;
        const updated = {
          ...d,
          available: newAvail,
          slots: d.slots.map((s) => ({ ...s, available: newAvail ? s.available : false })),
          expanded: false,
        };
        if (newAvail) {
          // Restore from defaultSlots (original availability from settings)
          const restore = d.defaultSlots.length > 0 ? d.defaultSlots : originalDays[i]?.slots ?? [];
          const hasAnyAvail = restore.some((s) => s.available);
          if (hasAnyAvail) {
            updated.slots = restore.map((os) => ({ ...os }));
          } else {
            // Day was rest by default — create an evening fallback so user can configure
            updated.slots = restore.map((os) => ({
              ...os,
              available: os.slot === "evening",
              location: os.slot === "evening" ? "home" : os.location,
            }));
          }
          updated.available = true;
          updated.expanded = true;
        }
        updated.summary = summarizeSlots(updated.slots, gyms);
        updated.modified = isDayModified(updated, i);
        return updated;
      })
    );
  }

  function toggleExpand(index: number) {
    setDays((prev) =>
      prev.map((d, i) => (i === index ? { ...d, expanded: !d.expanded } : d))
    );
  }

  function updateSlot(dayIndex: number, slotIndex: number, updates: Partial<EditableSlot>) {
    setDays((prev) =>
      prev.map((d, di) => {
        if (di !== dayIndex) return d;
        const newSlots = d.slots.map((s, si) => {
          if (si !== slotIndex) return s;
          const merged = { ...s, ...updates };
          // Ensure gym_id is always set when location is gym
          if (merged.location === "gym" && !merged.gym_id && gyms.length > 0) {
            merged.gym_id = gyms[0].gym_id ?? null;
          }
          return merged;
        });
        const hasAny = newSlots.some((s) => s.available);
        const updated = {
          ...d,
          slots: newSlots,
          available: hasAny,
          summary: summarizeSlots(newSlots, gyms),
        };
        updated.modified = isDayModified(updated, dayIndex);
        return updated;
      })
    );
  }

  // B330: ref-based lock — `disabled={saving}` alone loses a double tap
  // landing in the same React batch, which here would fire two
  // putWeeklyOverride writes for the same week.
  const { run: handleSave, busy: saving } = useSubmitLock(async () => {
    setError(null);
    try {
      const changedDays: Record<string, {
        available: boolean;
        slots?: Record<string, { available: boolean; location: string; gym_id?: string | null }>;
      }> = {};

      const longNames: Record<string, string> = {
        mon: "monday", tue: "tuesday", wed: "wednesday",
        thu: "thursday", fri: "friday", sat: "saturday", sun: "sunday",
      };

      for (const day of days) {
        if (!day.modified) continue;
        const key = longNames[day.day] || day.day;

        if (!day.available) {
          changedDays[key] = { available: false };
        } else {
          const slotsMap: Record<string, { available: boolean; location: string; gym_id?: string | null }> = {};
          for (const s of day.slots) {
            slotsMap[s.slot] = {
              available: s.available,
              location: s.location,
              ...(s.gym_id ? { gym_id: s.gym_id } : {}),
            };
          }
          changedDays[key] = { available: true, slots: slotsMap };
        }
      }

      await putWeeklyOverride(nextWeekStart, changedDays);
      onPlanUpdated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  });

  return (
    <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
      <DrawerContent className="max-h-[85vh]">
        <DrawerHeader>
          <DrawerTitle>Plan your week</DrawerTitle>
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
            <div className="space-y-1.5">
              {days.map((day, di) => {
                const hasSlots = day.slots.some((s) => s.available);
                return (
                  <div
                    key={day.day}
                    className={`rounded-lg border p-2.5 ${
                      day.modified ? "border-primary/50 bg-primary/5" : "border-border"
                    }`}
                  >
                    {/* Compact row */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold w-10 shrink-0">
                        {WEEKDAY_LABELS[day.day]}
                      </span>

                      {/* Rest toggle */}
                      <button
                        onClick={() => toggleDayRest(di)}
                        className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                          !day.available
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        }`}
                        title={day.available ? "Set as rest day" : "Restore availability"}
                      >
                        <Moon className="h-3 w-3" />
                        Rest
                      </button>

                      {/* Summary */}
                      {day.available && (
                        <button
                          onClick={() => toggleExpand(di)}
                          className="flex-1 text-left text-xs text-muted-foreground truncate hover:text-foreground transition-colors"
                        >
                          {day.summary}
                        </button>
                      )}
                      {!day.available && (
                        <span className="flex-1 text-xs text-muted-foreground italic">Day off</span>
                      )}

                      {/* Expand chevron */}
                      {day.available && hasSlots && (
                        <button onClick={() => toggleExpand(di)} className="p-1">
                          <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${day.expanded ? "rotate-180" : ""}`} />
                        </button>
                      )}

                      {day.modified && (
                        <span className="text-[10px] text-primary font-medium shrink-0">Modified</span>
                      )}
                    </div>

                    {/* Expanded slots */}
                    {day.expanded && day.available && (
                      <div className="mt-2 space-y-1.5 pl-12" onPointerDown={(e) => e.stopPropagation()}>
                        {day.slots.map((slot, si) => (
                          <div key={slot.slot} className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground w-14 shrink-0">
                              {SLOT_LABELS[slot.slot]}
                            </span>

                            {/* Available toggle */}
                            <button
                              onClick={() => updateSlot(di, si, { available: !slot.available })}
                              className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                                slot.available
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-muted text-muted-foreground"
                              }`}
                            >
                              {slot.available ? "On" : "Off"}
                            </button>

                            {/* Location buttons */}
                            {slot.available && (
                              <div className="flex gap-1">
                                {LOCATION_OPTIONS.map((opt) => {
                                  const isActive = slot.location === opt.value;
                                  const Icon = opt.icon;
                                  return (
                                    <button
                                      key={opt.value}
                                      onClick={() => {
                                        const defaultGym = opt.value === "gym" && gyms.length > 0 ? (gyms[0].gym_id ?? null) : null;
                                        updateSlot(di, si, {
                                          location: opt.value,
                                          gym_id: opt.value === "gym" ? (slot.gym_id || defaultGym) : null,
                                        });
                                      }}
                                      className={`flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                                        isActive
                                          ? "bg-primary text-primary-foreground"
                                          : "bg-muted text-muted-foreground hover:bg-muted/80"
                                      }`}
                                    >
                                      <Icon className="h-3 w-3" />
                                      {opt.label}
                                    </button>
                                  );
                                })}
                              </div>
                            )}

                            {/* Gym picker */}
                            {slot.available && slot.location === "gym" && gyms.length > 1 && (
                              <select
                                value={slot.gym_id ?? ""}
                                onChange={(e) => updateSlot(di, si, { gym_id: e.target.value || null })}
                                className="rounded border bg-background px-1.5 py-0.5 text-[10px] max-w-[100px]"
                              >
                                {gyms.map((g) => (
                                  <option key={g.gym_id ?? g.name} value={g.gym_id ?? ""}>
                                    {g.name}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <DrawerFooter>
          {hasChanges ? (
            <>
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
              <Button variant="ghost" size="sm" onClick={onClose}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={onClose}>
              Looks good
            </Button>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
