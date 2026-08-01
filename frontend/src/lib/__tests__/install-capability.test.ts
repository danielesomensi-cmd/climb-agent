import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getCapability,
  getIosBrowser,
  getPlatform,
  isInAppBrowser,
  isStandalone,
} from "@/lib/install";

/**
 * A260 — the install screen shows different *actions* per environment, and
 * getting the environment wrong is not cosmetic: an Instagram webview shown
 * "Add to Home Screen" steps asks for something the browser cannot do, and a
 * Chromium user shown iOS steps never sees the one-tap button they could have
 * had. These are the branches that decide which is which.
 */

const UA = {
  iphoneSafari:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
  iphoneChrome:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/122.0 Mobile/15E148 Safari/604.1",
  iphoneFirefox:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/124.0 Mobile/15E148 Safari/605.1.15",
  androidChrome:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
  instagram:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 320.0.0.0",
  facebook:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 FBAN/FBIOS;FBAV/450.0.0",
  linkedin:
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36 LinkedInApp",
  androidWebview:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP1A) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.0.0 Mobile wv Safari/537.36",
  desktopChrome:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  ipadOs:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
} as const;

/**
 * Tests run in vitest's default node environment (no jsdom), so the browser
 * globals are stubbed the way the rest of the suite does it — see
 * onboarding-draft-scope.test.ts. The detection helpers read `navigator` and
 * `window` at call time, not at import time, so a static import is fine.
 */
function setEnv(ua: string, opts?: { touchPoints?: number; standalone?: boolean }) {
  const nav = {
    userAgent: ua,
    maxTouchPoints: opts?.touchPoints ?? 0,
    standalone: opts?.standalone,
  };
  vi.stubGlobal("navigator", nav);
  vi.stubGlobal("window", {
    navigator: nav,
    matchMedia: (query: string) => ({
      matches: query.includes("standalone") ? Boolean(opts?.standalone) : false,
      media: query,
    }),
    addEventListener: () => {},
    removeEventListener: () => {},
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getPlatform", () => {
  it("detects android", () => {
    setEnv(UA.androidChrome);
    expect(getPlatform()).toBe("android");
  });

  it("detects iphone", () => {
    setEnv(UA.iphoneSafari);
    expect(getPlatform()).toBe("ios");
  });

  it("detects iPadOS, which lies and reports a desktop Mac UA", () => {
    setEnv(UA.ipadOs, { touchPoints: 5 });
    expect(getPlatform()).toBe("ios");
  });

  it("does not mistake a real Mac for an iPad", () => {
    setEnv(UA.desktopChrome, { touchPoints: 0 });
    expect(getPlatform()).toBe("desktop");
  });
});

describe("isInAppBrowser", () => {
  it.each([
    ["instagram", UA.instagram],
    ["facebook", UA.facebook],
    ["linkedin", UA.linkedin],
    ["android system webview", UA.androidWebview],
  ])("flags %s as a webview that cannot install", (_name, ua) => {
    setEnv(ua);
    expect(isInAppBrowser()).toBe(true);
  });

  it.each([
    ["safari", UA.iphoneSafari],
    ["chrome android", UA.androidChrome],
    ["chrome desktop", UA.desktopChrome],
  ])("does not flag %s", (_name, ua) => {
    setEnv(ua);
    expect(isInAppBrowser()).toBe(false);
  });
});

describe("getIosBrowser", () => {
  it("distinguishes Chrome and Firefox from Safari — all three carry 'Safari' in the UA", () => {
    setEnv(UA.iphoneChrome);
    expect(getIosBrowser()).toBe("chrome");
    setEnv(UA.iphoneFirefox);
    expect(getIosBrowser()).toBe("firefox");
    setEnv(UA.iphoneSafari);
    expect(getIosBrowser()).toBe("safari");
  });
});

describe("isStandalone", () => {
  it("is true when the display-mode media query matches", () => {
    setEnv(UA.androidChrome, { standalone: true });
    expect(isStandalone()).toBe(true);
  });

  it("is false in a normal browser tab", () => {
    setEnv(UA.androidChrome);
    expect(isStandalone()).toBe(false);
  });
});

describe("getCapability", () => {
  it("prefers the native prompt whenever the browser offered one", () => {
    setEnv(UA.androidChrome);
    expect(getCapability(true)).toBe("native-prompt");
  });

  it("reports an already-installed app before anything else", () => {
    // Chromium can still hold a deferred prompt in an installed window; the
    // user has nothing left to do, so 'installed' must win.
    setEnv(UA.androidChrome, { standalone: true });
    expect(getCapability(true)).toBe("installed");
  });

  it("routes social webviews out of the install steps", () => {
    setEnv(UA.instagram);
    expect(getCapability(false)).toBe("in-app-browser");
  });

  it("gives iOS Safari the manual Add to Home Screen path", () => {
    setEnv(UA.iphoneSafari);
    expect(getCapability(false)).toBe("ios-manual");
  });

  it("gives Chrome on iOS the same manual path (16.4+ supports it)", () => {
    setEnv(UA.iphoneChrome);
    expect(getCapability(false)).toBe("ios-manual");
  });

  it("does not promise Add to Home Screen on Firefox iOS, which lacks it", () => {
    setEnv(UA.iphoneFirefox);
    expect(getCapability(false)).toBe("unsupported");
  });

  it("falls back to browser-menu instructions on desktop with no prompt", () => {
    setEnv(UA.desktopChrome);
    expect(getCapability(false)).toBe("unsupported");
  });
});
