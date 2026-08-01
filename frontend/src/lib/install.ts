/**
 * A260 — PWA install friction.
 *
 * Two jobs:
 *
 * 1. **Capture the native install prompt.** Chromium fires `beforeinstallprompt`
 *    exactly once per page load, and typically *before* any route component has
 *    mounted. If nobody calls `preventDefault()` on it the event is gone, and
 *    with Next's client-side navigation there is no reload to get it back. So
 *    the listener is registered at module import time and the event is parked in
 *    a module-level store — `<InstallCapture />` in the root layout imports this
 *    file for that side effect alone. Where the prompt exists, installing is one
 *    tap on our own button instead of a hunt through the browser menu.
 *
 * 2. **Tell the user the truth about their browser.** iOS has no install API at
 *    all (Add to Home Screen is a Safari menu action, not something a page can
 *    trigger), and in-app browsers — Instagram, Facebook, LinkedIn — cannot
 *    install *anything*. Showing "Add to Home Screen" steps inside an Instagram
 *    webview asks for something the user physically cannot do; that path needs
 *    "open in the real browser" instead. Detection exists to route those cases,
 *    not to decorate.
 */

export type InstallPlatform = "ios" | "android" | "desktop";

/** How the page can be installed, if at all. Drives which UI branch renders. */
export type InstallCapability =
  | "installed" // already running as an installed app
  | "native-prompt" // beforeinstallprompt captured → one tap
  | "ios-manual" // iOS browser that has Add to Home Screen (Safari, Chrome 16.4+)
  | "in-app-browser" // social webview: cannot install, must open externally
  | "unsupported"; // e.g. Firefox on iOS — no install path at all

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

// ── Module-level store ───────────────────────────────────────────────────

let deferredPrompt: BeforeInstallPromptEvent | null = null;
let didInstall = false;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    // Required: without preventDefault Chromium shows (or suppresses) its own
    // mini-infobar and the event cannot be replayed later.
    e.preventDefault();
    deferredPrompt = e as BeforeInstallPromptEvent;
    emit();
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    didInstall = true;
    emit();
  });
}

export function subscribeInstall(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Snapshot for useSyncExternalStore — must be referentially stable. */
export function hasNativePrompt(): boolean {
  return deferredPrompt !== null;
}

export function wasInstalledThisSession(): boolean {
  return didInstall;
}

/**
 * Fire the browser's own install dialog. Returns the user's choice, or null if
 * no prompt was available. The event is single-use: Chromium rejects a second
 * `prompt()` on the same instance, so it is cleared either way.
 */
export async function promptInstall(): Promise<"accepted" | "dismissed" | null> {
  const evt = deferredPrompt;
  if (!evt) return null;
  deferredPrompt = null;
  emit();
  try {
    await evt.prompt();
    const { outcome } = await evt.userChoice;
    return outcome;
  } catch {
    return null;
  }
}

// ── Environment detection ────────────────────────────────────────────────

function ua(): string {
  if (typeof navigator === "undefined") return "";
  return navigator.userAgent || "";
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  // iOS Safari predates display-mode and only exposes this non-standard flag.
  return (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function getPlatform(): InstallPlatform {
  const s = ua();
  if (/android/i.test(s)) return "android";
  if (/iphone|ipad|ipod/i.test(s)) return "ios";
  // iPadOS 13+ reports a desktop Mac UA; touch points give it away.
  if (/macintosh/i.test(s) && typeof navigator !== "undefined" && navigator.maxTouchPoints > 1) {
    return "ios";
  }
  return "desktop";
}

/**
 * Social in-app webviews. These cannot install a PWA at all, so the only useful
 * instruction is "open this in your browser". Detection is UA-based and
 * therefore best-effort — a miss degrades to the normal instructions, which is
 * the same experience as today.
 */
export function isInAppBrowser(): boolean {
  const s = ua();
  if (/FBAN|FBAV|FB_IAB/i.test(s)) return true; // Facebook / Messenger
  if (/Instagram/i.test(s)) return true;
  if (/LinkedInApp/i.test(s)) return true;
  if (/Twitter|TwitterAndroid/i.test(s)) return true;
  if (/TikTok|musical_ly|BytedanceWebview/i.test(s)) return true;
  if (/Snapchat/i.test(s)) return true;
  if (/\bLine\//i.test(s)) return true;
  if (/Pinterest/i.test(s)) return true;
  // Android System WebView: has "wv" in the UA and is never a real browser.
  if (/Android.*\bwv\b/i.test(s)) return true;
  return false;
}

/**
 * Major iOS version, or null when the UA does not carry one (iPadOS pretending
 * to be a Mac reports `Version/17.4` instead of `OS 17_4`).
 *
 * B316: this is not trivia — iOS 26 moved Safari's Share button *out of the
 * toolbar* and into the `•••` menu next to the address bar, so the pre-26
 * instructions send the user hunting for an icon that is no longer there.
 * Callers that get null should fall back to the newer wording, since that is
 * where the installed base is heading.
 */
export function getIosMajorVersion(): number | null {
  const m = ua().match(/(?:iPhone )?OS (\d+)[_.]/);
  return m ? Number.parseInt(m[1], 10) : null;
}

/** Human-facing browser name, used only to name the right menu in the steps. */
export function getIosBrowser(): "safari" | "chrome" | "firefox" | "edge" | "other" {
  const s = ua();
  if (/CriOS/i.test(s)) return "chrome";
  if (/FxiOS/i.test(s)) return "firefox";
  if (/EdgiOS/i.test(s)) return "edge";
  if (/Safari/i.test(s)) return "safari";
  return "other";
}

/**
 * Single decision point for which UI to render. Order matters: an installed app
 * needs nothing, and an in-app browser must be caught before we hand out steps
 * it cannot follow.
 */
export function getCapability(nativePromptAvailable: boolean): InstallCapability {
  if (isStandalone() || wasInstalledThisSession()) return "installed";
  if (nativePromptAvailable) return "native-prompt";
  if (isInAppBrowser()) return "in-app-browser";
  if (getPlatform() === "ios") {
    // Firefox on iOS has no Add to Home Screen entry — pretending otherwise
    // sends the user looking for a menu item that does not exist.
    return getIosBrowser() === "firefox" ? "unsupported" : "ios-manual";
  }
  return "unsupported";
}
