import { defineConfig } from "vitest/config";
import path from "path";

// B323 — `.tsx` joins the glob so components can be rendered, not only pure
// helpers. The default environment stays **node**: the 44 pre-existing suites
// were written against it (`onboarding-draft-scope` leans on Node's own
// localStorage), and flipping the global default to jsdom to serve a handful of
// render tests would put every one of them on an environment it was never run
// on. Render suites opt in per file with `@vitest-environment jsdom`.
export default defineConfig({
  // `tsconfig.json` sets `jsx: "preserve"` because Next does its own transform;
  // esbuild would then hand raw JSX to the runtime. Telling it `automatic` here
  // is enough to render components — no `@vitejs/plugin-react`, which does not
  // accept the vite 7 that vitest 4 pulls in.
  esbuild: { jsx: "automatic" },
  test: {
    include: ["src/**/__tests__/**/*.test.ts", "src/**/__tests__/**/*.test.tsx"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
