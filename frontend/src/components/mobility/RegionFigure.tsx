"use client";

// A231 — Minimal body-silhouette pictogram with the target region highlighted.
// Pure inline SVG: crisp at any size, theme-aware, no image assets needed.

import { cn } from "@/lib/utils";

type Part =
  | "head" | "neck" | "torso" | "shoulderL" | "shoulderR"
  | "upperArmL" | "upperArmR" | "forearmL" | "forearmR" | "handL" | "handR"
  | "pelvis" | "thighL" | "thighR" | "calfL" | "calfR" | "footL" | "footR";

// Overlay bands drawn on top of the base silhouette for regions that map to
// a slice of a limb/torso rather than a whole part.
type Overlay = "chest" | "spineColumn" | "latL" | "latR" | "obliques" | "groin";

const REGION_PARTS: Record<string, { parts: Part[]; overlays: Overlay[] }> = {
  forearms_wrists: { parts: ["forearmL", "forearmR", "handL", "handR"], overlays: [] },
  hips_glutes: { parts: ["pelvis"], overlays: [] },
  chest_anterior_shoulder: { parts: ["shoulderL", "shoulderR"], overlays: ["chest"] },
  thoracic_spine: { parts: [], overlays: ["spineColumn"] },
  hip_flexors_quads: { parts: ["thighL", "thighR"], overlays: [] },
  adductors_groin: { parts: [], overlays: ["groin"] },
  lats: { parts: [], overlays: ["latL", "latR"] },
  shoulders_scapula: { parts: ["shoulderL", "shoulderR"], overlays: [] },
  hamstrings: { parts: ["thighL", "thighR"], overlays: [] },
  calves_ankles: { parts: ["calfL", "calfR", "footL", "footR"], overlays: [] },
  spine_rotation_obliques: { parts: [], overlays: ["obliques"] },
};

const BASE = "fill-muted-foreground/25";
const HI = "fill-violet-400";
const HI_SOFT = "fill-violet-400/80";

function partClass(part: Part, active: Set<Part>): string {
  return active.has(part) ? HI : BASE;
}

interface RegionFigureProps {
  region: string;
  className?: string;
}

export function RegionFigure({ region, className }: RegionFigureProps) {
  const mapping = REGION_PARTS[region] ?? { parts: [], overlays: [] };
  const active = new Set<Part>(mapping.parts);
  const overlays = new Set<Overlay>(mapping.overlays);

  return (
    <svg viewBox="0 0 100 180" className={cn("h-full w-auto", className)} aria-hidden>
      {/* head + neck */}
      <circle cx="50" cy="15" r="10" className={partClass("head", active)} />
      <rect x="46" y="25" width="8" height="7" rx="2" className={partClass("neck", active)} />
      {/* torso */}
      <rect x="34" y="31" width="32" height="48" rx="10" className={partClass("torso", active)} />
      {/* shoulders */}
      <circle cx="30" cy="39" r="7" className={partClass("shoulderL", active)} />
      <circle cx="70" cy="39" r="7" className={partClass("shoulderR", active)} />
      {/* upper arms */}
      <rect x="19" y="42" width="9" height="28" rx="4.5" className={partClass("upperArmL", active)} />
      <rect x="72" y="42" width="9" height="28" rx="4.5" className={partClass("upperArmR", active)} />
      {/* forearms */}
      <rect x="16" y="71" width="8" height="25" rx="4" className={partClass("forearmL", active)} />
      <rect x="76" y="71" width="8" height="25" rx="4" className={partClass("forearmR", active)} />
      {/* hands */}
      <circle cx="20" cy="101" r="4.5" className={partClass("handL", active)} />
      <circle cx="80" cy="101" r="4.5" className={partClass("handR", active)} />
      {/* pelvis */}
      <rect x="35" y="80" width="30" height="15" rx="7" className={partClass("pelvis", active)} />
      {/* thighs */}
      <rect x="36" y="95" width="12" height="36" rx="6" className={partClass("thighL", active)} />
      <rect x="52" y="95" width="12" height="36" rx="6" className={partClass("thighR", active)} />
      {/* calves */}
      <rect x="37.5" y="132" width="10" height="30" rx="5" className={partClass("calfL", active)} />
      <rect x="52.5" y="132" width="10" height="30" rx="5" className={partClass("calfR", active)} />
      {/* feet */}
      <ellipse cx="41" cy="167" rx="8" ry="4.5" className={partClass("footL", active)} />
      <ellipse cx="59" cy="167" rx="8" ry="4.5" className={partClass("footR", active)} />

      {/* overlays */}
      {overlays.has("chest") && (
        <rect x="36" y="34" width="28" height="16" rx="7" className={HI_SOFT} />
      )}
      {overlays.has("spineColumn") && (
        <rect x="46" y="33" width="8" height="34" rx="4" className={HI} />
      )}
      {overlays.has("latL") && (
        <rect x="34" y="46" width="8" height="28" rx="4" className={HI_SOFT} />
      )}
      {overlays.has("latR") && (
        <rect x="58" y="46" width="8" height="28" rx="4" className={HI_SOFT} />
      )}
      {overlays.has("obliques") && (
        <rect x="36" y="58" width="28" height="16" rx="7" className={HI_SOFT} />
      )}
      {overlays.has("groin") && (
        <>
          <rect x="44" y="93" width="12" height="10" rx="5" className={HI} />
          <rect x="45" y="98" width="4.5" height="22" rx="2.2" className={HI_SOFT} />
          <rect x="50.5" y="98" width="4.5" height="22" rx="2.2" className={HI_SOFT} />
        </>
      )}
    </svg>
  );
}
