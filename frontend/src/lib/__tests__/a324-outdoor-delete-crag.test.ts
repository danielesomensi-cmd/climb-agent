import { describe, it, expect, vi, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { deleteOutdoorLog } from "@/lib/api";
import { stripComments } from "./helpers/source-scan";

/**
 * A324 — residual of B401 (B-OUTDOOR-CRAG-PICKER point 1): the Outdoor History
 * trash deletes ONE crag of a day. Without `spot_name` the server refuses a
 * multi-crag day (409) and the page showed «Could not delete session».
 */

function stubFetch() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      urls.push(`${init?.method ?? "GET"} ${url}`);
      return new Response(JSON.stringify({ status: "ok", date: "2026-11-01" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return urls;
}

afterEach(() => vi.unstubAllGlobals());

describe("A324 — DELETE /api/outdoor/log/{date} names the crag", () => {
  it("sends spot_name, URL-encoded", async () => {
    const urls = stubFetch();
    await deleteOutdoorLog("2026-11-01", "La Crique & Co");
    expect(urls).toHaveLength(1);
    expect(urls[0]).toMatch(/^DELETE .*\/api\/outdoor\/log\/2026-11-01\?spot_name=La%20Crique%20%26%20Co$/);
  });

  it("without a crag it stays the date-only delete", async () => {
    const urls = stubFetch();
    await deleteOutdoorLog("2026-11-01");
    expect(urls[0]).toMatch(/\/api\/outdoor\/log\/2026-11-01$/);
  });

  it("Outdoor History passes each row's crag, and confirms per crag, not per date", () => {
    const code = stripComments(
      readFileSync(join(process.cwd(), "src", "app/(main)/outdoor/page.tsx"), "utf8"),
    );
    expect(code).toContain("handleDeleteSession(s.date, s.spot_name)");
    expect(code).toMatch(/deleteOutdoorLog\(date, spotName/);
    expect(code).not.toMatch(/deleteOutdoorLog\(date\)/);
    expect(code).not.toContain("confirmDeleteDate");
  });
});
