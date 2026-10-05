/**
 * A300 — the adaptive weekly structure, client side (pure helpers for the
 * Settings availability editor).
 *
 * Each availability slot may carry three optional fields: `role`
 * (`primary` | `complementary` | `any`), `max_minutes` (10..240) and `focus`
 * (a pinned complementary family). `planning_prefs.complementary_rotation` is
 * the ordered list of families the engine pairs with the complementary slots,
 * day by day, by itself (no fixed weekday).
 *
 * Hard rule (A300): a user who never touches these fields must send exactly
 * what they sent before — their plan stays byte-identical. So a field is only
 * written when the user set it, and "clearing" a field that was never stored
 * removes the key instead of writing a default.
 */
import type { FocusFamily, SlotRole } from "@/lib/types";

export const SLOT_ROLES: SlotRole[] = ["any", "primary", "complementary"];
export const ROLE_LABELS: Record<SlotRole, string> = {
  any: "Any",
  primary: "Primary",
  complementary: "Complementary",
};
export const MAX_MINUTES_RANGE: [number, number] = [10, 240];
export const DEFAULT_ROTATION: FocusFamily[] = ["legs", "hiit", "z2", "upper_push_arms"];
export const MAX_ROTATION_LENGTH = 21;

export type StructuredSlot = {
  available: boolean;
  preferred_location: string;
  gym_id?: string;
  other_activity_name?: string;
  reduce_intensity_after?: boolean;
  role?: SlotRole | null;
  max_minutes?: number | null;
  focus?: FocusFamily | null;
};

type Initial = Partial<StructuredSlot> | null | undefined;

function hasKey(obj: Initial, key: keyof StructuredSlot): boolean {
  return !!obj && Object.prototype.hasOwnProperty.call(obj, key) && obj[key] != null;
}

/**
 * The slot with *key* set to *value*. A "cleared" value (`any` role, empty
 * minutes, auto focus) deletes the key when the stored slot never had it, and
 * writes the neutral value when it did — the server deep-merges, so only an
 * explicit value overwrites what is stored.
 */
function setField<K extends "role" | "max_minutes" | "focus">(
  slot: StructuredSlot,
  key: K,
  value: StructuredSlot[K],
  cleared: boolean,
  initial: Initial,
  neutral: StructuredSlot[K],
): StructuredSlot {
  const next: StructuredSlot = { ...slot };
  if (!cleared) {
    next[key] = value;
  } else if (hasKey(initial, key)) {
    next[key] = neutral;
  } else {
    delete next[key];
  }
  return next;
}

export function withRole(slot: StructuredSlot, role: SlotRole, initial: Initial): StructuredSlot {
  let next = setField(slot, "role", role, role === "any", initial, "any");
  // A pinned focus only means something on a complementary slot.
  if (role !== "complementary" && next.focus != null) next = withFocus(next, null, initial);
  return next;
}

export function withMaxMinutes(slot: StructuredSlot, minutes: number | null, initial: Initial): StructuredSlot {
  return setField(slot, "max_minutes", minutes, minutes == null, initial, null);
}

export function withFocus(slot: StructuredSlot, focus: FocusFamily | null, initial: Initial): StructuredSlot {
  return setField(slot, "focus", focus, focus == null, initial, null);
}

/** Parse the max-minutes input: null = empty (no limit), NaN = invalid. */
export function parseMaxMinutes(raw: string): number | null {
  const t = raw.trim();
  if (t === "") return null;
  if (!/^\d+$/.test(t)) return NaN;
  const n = Number(t);
  const [lo, hi] = MAX_MINUTES_RANGE;
  return n >= lo && n <= hi ? n : NaN;
}

/** The role the engine will read (absent / null / unknown = any). */
export function effectiveRole(slot: Partial<StructuredSlot> | null | undefined): SlotRole {
  const r = slot?.role;
  return r === "primary" || r === "complementary" ? r : "any";
}

/** A slot the primary passes can use: available, not another sport, not complementary. */
export function isPrimaryCapable(slot: Partial<StructuredSlot> | null | undefined): boolean {
  return !!slot?.available && slot.preferred_location !== "other_sport" && effectiveRole(slot) !== "complementary";
}

export function isComplementary(slot: Partial<StructuredSlot> | null | undefined): boolean {
  return !!slot?.available && slot.preferred_location !== "other_sport" && effectiveRole(slot) === "complementary";
}

/** The rotation the engine will use for the general phase (absent = all four). */
export function effectiveRotation(raw: unknown): FocusFamily[] {
  if (!Array.isArray(raw)) return [...DEFAULT_ROTATION];
  return raw.filter((f): f is FocusFamily => (DEFAULT_ROTATION as string[]).includes(f as string));
}

export function moveItem<T>(list: T[], index: number, delta: -1 | 1): T[] {
  const to = index + delta;
  if (index < 0 || index >= list.length || to < 0 || to >= list.length) return list;
  const next = [...list];
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

/** Short label for the read-only availability summary in Settings. */
export function slotStructureLabel(slot: Partial<StructuredSlot> | null | undefined): string {
  const parts: string[] = [];
  const role = effectiveRole(slot);
  if (role !== "any") parts.push(role === "primary" ? "primary" : "compl.");
  if (typeof slot?.max_minutes === "number") parts.push(`≤${slot.max_minutes}′`);
  return parts.join(" ");
}
