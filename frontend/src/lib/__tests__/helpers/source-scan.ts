import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Shared helper for the structural guards.
 *
 * Written after making the same mistake three times in one session: a guard
 * that greps the sources for a forbidden pattern matches the COMMENT that
 * explains why the pattern is forbidden, so the test fails on its own
 * documentation. Strip comments first — these guards are about code.
 */
export function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const SKIP_DIRS = new Set(["node_modules", ".next", "__tests__"]);

/** Every .ts/.tsx file under `dir`, as `{ path, code }` with comments removed. */
export function sourceFiles(dir: string): Array<{ path: string; code: string }> {
  const out: Array<{ path: string; code: string }> = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(entry)) out.push(...sourceFiles(full));
      continue;
    }
    if (!/\.tsx?$/.test(entry)) continue;
    out.push({ path: full, code: stripComments(readFileSync(full, "utf8")) });
  }
  return out;
}

/** `file:line` for every code line matching `pattern`. */
export function findInSources(dir: string, pattern: RegExp): string[] {
  const hits: string[] = [];
  for (const { path, code } of sourceFiles(dir)) {
    code.split("\n").forEach((line, i) => {
      if (pattern.test(line)) hits.push(`${path.replace(dir, "src")}:${i + 1}`);
      pattern.lastIndex = 0;
    });
  }
  return hits;
}
