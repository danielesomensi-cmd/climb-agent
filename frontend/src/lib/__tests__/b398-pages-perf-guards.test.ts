import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { stripComments } from "./helpers/source-scan";

/**
 * B398 — structural guards for the request / bundle cuts on the pages other
 * than /today and the guided session. Behaviour is covered elsewhere (O1, O2,
 * O13 have their own suites); these pin the shape so a refactor does not
 * silently bring a request or a static import back.
 */
const src = (rel: string) => stripComments(readFileSync(join(process.cwd(), "src", rel), "utf8"));

describe("B398 — /settings", () => {
  const code = src("app/(main)/settings/page.tsx");

  it("O4: a PUT /api/state is never followed by a second GET of the state", () => {
    // The response of putState is written into the cache instead.
    expect(code).not.toMatch(/await putState\([^;]*\);\s*await refresh\(\);/);
    expect(code).toContain("qc.setQueryData(queryKeys.state, next)");
  });

  it("O8: the editors and dialogs opened by a tap are lazy chunks", () => {
    for (const mod of [
      "availability-editor",
      "equipment-editor",
      "goal-editor",
      "profile-assessment-editor",
      "start-new-macrocycle-dialog",
    ]) {
      expect(code).not.toMatch(new RegExp(`^import \\{[^}]*\\} from "@/components/settings/${mod}"`, "m"));
      expect(code).toContain(`import("@/components/settings/${mod}")`);
    }
  });

  it("O11: the spots come from the React Query cache", () => {
    expect(code).not.toContain("getOutdoorSpots(");
    expect(code).toContain("useOutdoorSpots(authReady)");
  });
});

describe("B398 — /outdoor", () => {
  const code = src("app/(main)/outdoor/page.tsx");

  it("O5: the quick log goes through the parallel resolver with cached spots", () => {
    expect(code).toContain("resolveOutdoorLogTarget(today, () => fetchOutdoorSpots(qc))");
    expect(code).not.toContain("getOutdoorSpots(");
  });

  it("O9: OutdoorLogForm is not in the page's first load", () => {
    expect(code).not.toMatch(/^import OutdoorLogForm from/m);
    expect(code).toMatch(/const OutdoorLogForm = dynamic\(/);
  });
});

describe("B398 — /coach Add & run (O6)", () => {
  const code = src("app/(main)/coach/page.tsx");

  it("reads the current week through the cache, not a bare GET", () => {
    expect(code).not.toMatch(/await getWeek\(0\)/);
    expect(code).toContain("queryKey: queryKeys.week(0)");
  });

  it("starts today's read of the session before the add, not after it", () => {
    const read = code.indexOf("getCustomSession(created.id, today)");
    const add = code.indexOf("await applyEvents(");
    expect(read).toBeGreaterThan(-1);
    expect(add).toBeGreaterThan(read);
  });
});

describe("B398 — /reports/weekly (O7)", () => {
  it("subscribes to the heatmap at page level, in parallel with the report", () => {
    const code = src("app/(main)/reports/weekly/page.tsx");
    expect(code).toMatch(/useMonthlyHeatmap\(.*, authReady\);/);
  });
});

describe("B398 — /plan (O12)", () => {
  it("the stale check is the cached useStateStatus query", () => {
    const code = src("app/(main)/plan/page.tsx");
    expect(code).not.toContain("getStateStatus");
    expect(code).toContain("useStateStatus(authReady)");
  });
});

describe("B398 — vaul off the first load (O10)", () => {
  it("the More drawer is not imported statically by the nav", () => {
    const nav = src("components/layout/bottom-nav.tsx");
    expect(nav).not.toContain("@/components/ui/drawer");
    expect(nav).toMatch(/dynamic\(\(\) => import\("\.\/more-drawer"\)/);
  });

  it.each(["app/(main)/plan/page.tsx", "app/(main)/settings/page.tsx"])(
    "%s loads the regen sheet (the other vaul user) lazily",
    (rel) => {
      const code = src(rel);
      expect(code).not.toMatch(/^import \{[^}]*\} from "@\/components\/training\/regenerate-plan-sheet"/m);
      expect(code).toContain('import("@/components/training/regenerate-plan-sheet")');
    },
  );
});
