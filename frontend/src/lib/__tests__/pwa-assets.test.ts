import { describe, it, expect } from "vitest";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { CORE_EXERCISES } from "@/components/circuit/circuit-exercises";

const PUBLIC = join(process.cwd(), "public");

/**
 * A245 F-4 (F13) — the circuit timer's exercise images.
 *
 * Two of them were 1.7 MB PNGs at 1536px, rendered into a 140px-tall slot: on
 * gym 3G a single image took 10+ seconds and stalled the exercise card
 * mid-circuit.
 */
describe("exercise images", () => {
  /**
   * Three exercises (36_straddle_l_sit, 37_v_up_hold, 40_arch_body_hold) have
   * their `image:` line commented out with a "TODO: add image" — deliberate
   * placeholders, not broken references. Reading the array rather than grepping
   * the file is what tells the difference: a grep matches the comments too.
   */
  const referenced = CORE_EXERCISES
    .map((e) => e.image)
    .filter((i): i is string => typeof i === "string" && i.length > 0);

  it("references at least one image (guards against an empty catalog)", () => {
    expect(referenced.length).toBeGreaterThan(10);
  });

  it("ships every image it actually references", () => {
    const missing = referenced
      .filter((img) => !existsSync(join(PUBLIC, "exercises", "core", img)))
      .sort();
    expect(missing).toEqual([]);
  });

  it("keeps every shipped image under 350 KB", () => {
    const tooBig = referenced
      .map((img) => join(PUBLIC, "exercises", "core", img))
      .filter((p) => existsSync(p) && statSync(p).size > 350_000)
      .map((p) => `${p.split("/").pop()} (${Math.round(statSync(p).size / 1024)} KB)`);
    expect(tooBig).toEqual([]);
  });
});

/** A245 F-4 (F43) — manifest correctness. */
describe("PWA manifest", () => {
  const manifest = JSON.parse(readFileSync(join(PUBLIC, "manifest.json"), "utf8"));

  it("agrees with the viewport theme colour", () => {
    // layout.tsx sets viewport.themeColor to #0f121a; the manifest used to
    // declare #e94560, a colour the app never renders.
    const layout = readFileSync(join(process.cwd(), "src/app/layout.tsx"), "utf8");
    const m = layout.match(/themeColor:\s*"(#[0-9a-fA-F]{6})"/);
    expect(m, "layout.tsx must declare a themeColor").not.toBeNull();
    expect(manifest.theme_color.toLowerCase()).toBe(m![1].toLowerCase());
  });

  it("declares a maskable icon so Android does not crop the logo badly", () => {
    const maskable = manifest.icons.filter((i: { purpose?: string }) =>
      i.purpose?.split(" ").includes("maskable"),
    );
    expect(maskable.length).toBeGreaterThan(0);
  });

  it("ships every icon file it declares", () => {
    for (const icon of manifest.icons as Array<{ src: string }>) {
      expect(existsSync(join(PUBLIC, icon.src)), `missing ${icon.src}`).toBe(true);
    }
  });
});
