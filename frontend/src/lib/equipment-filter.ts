import type { Exercise } from "@/lib/types";

// ─── Equipment expansion (mirrors backend get_location_equipment) ────

/**
 * Expand raw equipment list with implicit items, matching the backend logic
 * in resolve_session.py get_location_equipment() + resolve_session().
 */
export function expandEquipment(raw: string[], location: string): Set<string> {
  const norm = (s: string) => s.trim().toLowerCase();
  const equip = new Set(raw.map(norm));

  // Always-available virtual equipment
  equip.add("floor");

  // Weight subtypes imply canonical "weight"
  const weightSubtypes = new Set(["dumbbell", "kettlebell", "barbell"]);
  for (const w of weightSubtypes) {
    if (equip.has(w)) { equip.add("weight"); break; }
  }

  // loading_pin → hangboard alias
  if (equip.has("loading_pin")) equip.add("hangboard");

  // Every gym has a pullup bar
  if (location === "gym") equip.add("pullup_bar");

  return equip;
}

/**
 * Check whether an exercise is compatible with the available equipment.
 * Mirrors pick_best_exercise_p0() Stage 2 in resolve_session.py.
 */
export function isExerciseCompatible(ex: Exercise, available: Set<string>): boolean {
  const norm = (s: string) => s.trim().toLowerCase();

  // AND: ALL items in equipment_required must be available
  const req = (ex.equipment_required ?? []).map(norm).filter(Boolean);
  if (req.length > 0 && !req.every((r) => available.has(r))) return false;

  // OR: at least ONE item in equipment_required_any must be available
  const reqAny = (ex.equipment_required_any ?? []).map(norm).filter(Boolean);
  if (reqAny.length > 0 && !reqAny.some((r) => available.has(r))) return false;

  return true;
}
