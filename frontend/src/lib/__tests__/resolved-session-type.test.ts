import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { stripComments } from "./helpers/source-scan";

/**
 * A245 G-6 (F23) — the `ResolvedSession` type must describe the payload the
 * backend actually sends.
 *
 * It used to declare a top-level `blocks: [{ block_name, exercises }]`. The
 * real shape nests everything under `resolved_session` and names the fields
 * `block_uid` / `selected_exercises`. The single consumer called
 * `resolved.blocks.map(...)` — a guaranteed TypeError that never fired only
 * because nothing links to `/session/[id]`.
 *
 * The field names are checked against the Python that produces them, so a
 * backend rename breaks this test instead of rendering `undefined` on the
 * training screen.
 */
const REPO = join(process.cwd(), "..");
const resolver = readFileSync(
  join(REPO, "backend/engine/resolve_session.py"),
  "utf8",
);
const types = stripComments(
  readFileSync(join(process.cwd(), "src/lib/types.ts"), "utf8"),
);

describe("ResolvedSession mirrors the backend payload", () => {
  it("keeps the envelope keys the resolver emits", () => {
    for (const key of ["session_instance_version", "context", "resolved_session"]) {
      expect(resolver, `backend no longer emits ${key}`).toContain(`"${key}"`);
      expect(types, `types.ts is missing ${key}`).toContain(key);
    }
  });

  it("uses block_uid and selected_exercises, not the invented names", () => {
    expect(resolver).toContain('"block_uid"');
    expect(resolver).toContain('"selected_exercises"');
    expect(types).toContain("block_uid");
    expect(types).toContain("selected_exercises");
  });

  it("no longer declares the fictional block_name / exercises pair", () => {
    expect(types).not.toContain("block_name");
  });

  it("nests blocks under resolved_session, not at the top level", () => {
    const decl = types.slice(types.indexOf("export interface ResolvedSession {"));
    const body = decl.slice(0, decl.indexOf("\n}"));
    // `blocks` must appear only inside the resolved_session member.
    const beforeNested = body.slice(0, body.indexOf("resolved_session"));
    expect(beforeNested).not.toContain("blocks");
  });

  it("the consumer reads the nested path", () => {
    const page = stripComments(
      readFileSync(join(process.cwd(), "src/app/(main)/session/[id]/page.tsx"), "utf8"),
    );
    expect(page).toContain("resolved.resolved_session.blocks");
    expect(page).not.toMatch(/resolved\.blocks/);
  });
});
