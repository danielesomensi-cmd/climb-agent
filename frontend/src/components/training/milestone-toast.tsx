"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { markMilestoneSeen } from "@/lib/api";
import { useMilestones } from "@/lib/hooks/queries";

/**
 * A239 (A-GAMIFY-02): celebration toasts on /today for freshly unlocked
 * milestones. Anti-spam rule: a retroactive first evaluation can unlock many
 * at once — more than 2 unseen collapse into one summary toast pointing to
 * the Plan gallery; all get marked seen either way. Renders nothing.
 *
 * B293 (interruption queue): `enabled` gates firing — /today keeps it false
 * until the phase-celebration modal has settled/closed, so the toast never
 * stacks on top of it. Unseen milestones are not lost: they stay unseen and
 * fire on the next enabled mount.
 */
export function MilestoneToast({ enabled = true }: { enabled?: boolean }) {
  const { data } = useMilestones();
  const firedRef = useRef(false);

  useEffect(() => {
    if (!enabled || firedRef.current || !data) return;
    const unseen = data.milestones.filter((m) => m.unlocked && !m.seen);
    if (unseen.length === 0) return;
    firedRef.current = true;

    if (unseen.length > 2) {
      toast.success(`🏆 ${unseen.length} milestones unlocked!`, {
        description: "See them all on your Plan page.",
        duration: 6000,
      });
    } else {
      for (const m of unseen) {
        const grade = m.context?.grade ? ` ${m.context.grade}` : "";
        toast.success(`${m.icon} ${m.name}${grade}`, {
          description: m.description,
          duration: 6000,
        });
      }
    }
    for (const m of unseen) {
      markMilestoneSeen(m.id).catch(() => {});
    }
  }, [data, enabled]);

  return null;
}
