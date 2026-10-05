import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "fs";
import path from "path";

/**
 * A301 — guards are alerts: a user action always goes through. The "Add hard
 * anyway" toast, the force-confirm dialog and the "session eased / next day
 * eased" toasts implied that the app had blocked or downgraded something, and
 * must not come back.
 */
const root = path.resolve(__dirname, "../../");
const read = (rel: string) => readFileSync(path.join(root, rel), "utf8");

const PAGES = ["app/(main)/week/page.tsx", "app/(main)/today/page.tsx"];

describe("A301 — no force / downgrade UI", () => {
  it("the force-confirm dialog is gone", () => {
    expect(existsSync(path.join(root, "components/training/force-hard-dialog.tsx"))).toBe(false);
  });

  it.each(PAGES)("%s has no force retry nor downgrade toast", (rel) => {
    const src = read(rel);
    expect(src).not.toMatch(/Add hard anyway/);
    expect(src).not.toMatch(/force:\s*true/);
    expect(src).not.toMatch(/ForceHardDialog/);
    expect(src).not.toMatch(/"Session adjusted"|"Next day eased"|"Plan adjusted"/);
    // Alerts are never shown through the error state (it hides the whole plan).
    expect(src).not.toMatch(/setError\(result\.warnings/);
  });

  it.each(PAGES)("%s renders the alerts card and passes the alerts to the day cards", (rel) => {
    const src = read(rel);
    expect(src).toMatch(/<WeekAlertsCard/);
    expect(src).toMatch(/guardWarnings=\{guardWarnings\}/);
  });

  it("the quick-add client no longer sends force", () => {
    const api = read("lib/api.ts");
    expect(api).not.toMatch(/force\?: boolean; \/\/ A254/);
    expect(api).not.toMatch(/export function quickAddCanForce/);
  });
});
