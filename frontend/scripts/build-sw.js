#!/usr/bin/env node
/**
 * build-sw.js — Generate frontend/public/sw.js from sw.template.js with a
 * unique CACHE_NAME per build.
 *
 * Why: Without per-build cache invalidation, PWA users keep serving stale JS
 * bundles after every deploy because the browser only re-installs sw.js when
 * its bytes change. Injecting a unique build id forces a new SW install on
 * every Vercel deploy → activate event purges old caches.
 *
 * Build id source priority:
 *   1. VERCEL_GIT_COMMIT_SHA (Vercel deployments)
 *   2. GITHUB_SHA (CI fallback)
 *   3. local git rev-parse HEAD
 *   4. timestamp fallback (dev / detached state)
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const TEMPLATE = path.join(__dirname, "..", "public", "sw.template.js");
const OUTPUT = path.join(__dirname, "..", "public", "sw.js");

function getBuildId() {
  if (process.env.VERCEL_GIT_COMMIT_SHA) {
    return process.env.VERCEL_GIT_COMMIT_SHA.slice(0, 12);
  }
  if (process.env.GITHUB_SHA) {
    return process.env.GITHUB_SHA.slice(0, 12);
  }
  try {
    return execSync("git rev-parse HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim()
      .slice(0, 12);
  } catch {
    return `dev-${Date.now()}`;
  }
}

const buildId = getBuildId();

if (!fs.existsSync(TEMPLATE)) {
  console.error(`[build-sw] template not found: ${TEMPLATE}`);
  process.exit(1);
}

const template = fs.readFileSync(TEMPLATE, "utf8");
if (!template.includes("__BUILD_ID__")) {
  console.error("[build-sw] template missing __BUILD_ID__ placeholder");
  process.exit(1);
}

const output = template.replace(/__BUILD_ID__/g, buildId);
fs.writeFileSync(OUTPUT, output);
console.log(`[build-sw] wrote sw.js with CACHE_NAME=climb-agent-${buildId}`);
