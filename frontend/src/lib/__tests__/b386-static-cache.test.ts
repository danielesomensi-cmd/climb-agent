import { describe, it, expect } from "vitest";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * B386 — a deploy that changed nothing must not re-download the app.
 *
 * Two halves: the service worker keeps content-addressed assets across deploys,
 * and Vercel does not rebuild the PWA for commits that do not touch frontend/.
 */
const SW = readFileSync(join(process.cwd(), "public/sw.template.js"), "utf8");

const constValue = (name: string): string => {
  const m = SW.match(new RegExp(`const ${name} = ([^;]+);`));
  if (!m) throw new Error(`${name} not found in sw.template.js`);
  return m[1];
};

describe("service worker — version-agnostic caches", () => {
  it("names the static and image caches without the build id", () => {
    expect(constValue("STATIC_CACHE_NAME")).not.toMatch(/__BUILD_ID__|CACHE_NAME/);
    expect(constValue("IMAGE_CACHE_NAME")).not.toMatch(/__BUILD_ID__|CACHE_NAME/);
  });

  it("keeps the per-build cache for shells (CACHE_NAME still carries the SHA)", () => {
    expect(constValue("CACHE_NAME")).toContain("__BUILD_ID__");
  });

  it("does not purge the agnostic caches on activate", () => {
    // B396 added the Clerk scripts' cache to the survivors.
    expect(SW).toMatch(/new Set\(\[CACHE_NAME, STATIC_CACHE_NAME, IMAGE_CACHE_NAME, CLERK_CACHE_NAME\]\)/);
  });

  it("serves /_next/static/* from the agnostic cache, before the per-build branch", () => {
    const hashed = SW.indexOf('url.pathname.startsWith("/_next/static/")');
    const generic = SW.indexOf("url.pathname.match(/\\.(js|css|png|jpg|svg|woff2?|ico)$/)");
    expect(hashed).toBeGreaterThan(0);
    expect(generic).toBeGreaterThan(hashed);
    expect(SW.slice(hashed, generic)).toContain("hashedStaticCacheFirst(request)");
  });

  it("bounds both agnostic caches and revalidates unhashed images", () => {
    expect(SW).toMatch(/fetchAndStore\(STATIC_CACHE_NAME, request, STATIC_CACHE_MAX_ENTRIES\)/);
    expect(SW).toMatch(/isOlderThan\(cached, IMAGE_REVALIDATE_MS\)/);
  });
});

describe("vercel.json ignoreCommand", () => {
  const vercel = JSON.parse(readFileSync(join(process.cwd(), "vercel.json"), "utf8"));
  const script = join(process.cwd(), "scripts/vercel-ignore-build.sh");

  it("runs the ignore script", () => {
    expect(vercel.ignoreCommand).toBe("sh scripts/vercel-ignore-build.sh");
    expect(readFileSync(script, "utf8")).toContain("VERCEL_GIT_PREVIOUS_SHA");
  });

  /** A throwaway repo shaped like ours: root + frontend/. Returns the exit code. */
  function scenario(steps: (commit: (file: string, msg: string) => string) => { base: string }) {
    const dir = mkdtempSync(join(tmpdir(), "b386-ignore-"));
    const git = (...a: string[]) =>
      execFileSync("git", a, { cwd: dir, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    try {
      git("init", "-q");
      git("config", "user.email", "t@t");
      git("config", "user.name", "t");
      mkdirSync(join(dir, "frontend"));
      let n = 0;
      const commit = (file: string, msg: string) => {
        writeFileSync(join(dir, file), String(n++));
        git("add", "-A");
        git("commit", "-q", "-m", msg);
        return git("rev-parse", "HEAD");
      };
      commit("frontend/a.ts", "init");
      const { base } = steps(commit);
      const r = spawnSync("sh", [script], {
        cwd: join(dir, "frontend"),
        env: { ...process.env, VERCEL_GIT_PREVIOUS_SHA: base },
      });
      return r.status;
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }

  it("skips (exit 0) when only docs/backend changed since the last deploy", () => {
    expect(
      scenario((c) => {
        const base = c("frontend/a.ts", "frontend");
        c("README.md", "sync: contatori");
        c("backend.py", "backend");
        return { base };
      }),
    ).toBe(0);
  });

  it("builds (exit 1) when a frontend commit is followed by a sync commit in one push", () => {
    // The HEAD^..HEAD form would see only the sync commit and skip this.
    expect(
      scenario((c) => {
        const base = c("README.md", "previous deploy");
        c("frontend/a.ts", "B999: frontend");
        c("README.md", "sync: contatori");
        return { base };
      }),
    ).toBe(1);
  });

  it("builds when there is no previous deployment SHA (first deploy of a branch)", () => {
    expect(scenario(() => ({ base: "" }))).toBe(1);
  });

  it("builds when the previous SHA is not in the clone", () => {
    expect(scenario(() => ({ base: "0123456789abcdef0123456789abcdef01234567" }))).toBe(1);
  });
});
