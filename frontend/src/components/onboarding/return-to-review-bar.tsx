"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";

/**
 * A245 Phase D (F47) — tapping "Edit" on the review screen dropped the user
 * back into the wizard with no way home: getting to review again meant tapping
 * Next through every remaining step, up to 10 taps to fix one field.
 *
 * Rendered by the onboarding layout, so it works on EVERY step — including the
 * ones that still have bespoke Back/Next footers — rather than needing each
 * page to be converted first.
 *
 * The onboarding context saves on every `update()`, so leaving via this bar
 * cannot lose the edit.
 */
export function ReturnToReviewBar() {
  const router = useRouter();
  const params = useSearchParams();

  if (params.get("from") !== "review") return null;

  return (
    <div className="sticky top-0 z-30 border-b border-primary/30 bg-primary/10 px-4 py-2 backdrop-blur">
      <div className="mx-auto flex max-w-lg items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground">Editing from summary</span>
        <Button
          size="sm"
          variant="outline"
          className="min-h-[36px] shrink-0 text-xs"
          onClick={() => router.push("/onboarding/review")}
        >
          Done — back to summary
        </Button>
      </div>
    </div>
  );
}
