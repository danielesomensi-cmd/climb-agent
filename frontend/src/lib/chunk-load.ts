import { toast } from "sonner";

/**
 * B396/B398 review (round 2) — what to tell the athlete when a lazily loaded
 * piece of UI (next/dynamic) could not be fetched.
 *
 * The failure is final for the life of the page: React.lazy keeps the rejected
 * import, and the Turbopack runtime caches the failed chunk as well, so a
 * second tap — even back online — gets the same error. Offline, the honest
 * answer is that it needs a connection. Online, the only way back is a reload
 * (the service worker then serves or fetches the chunk), and an installed iOS
 * PWA has no reload button: the toast carries one.
 */
export const CHUNK_OFFLINE_MESSAGE = "Needs a connection — reload the app once you're back online";
export const CHUNK_RELOAD_MESSAGE = "Couldn't load this — reload the app";

export function notifyChunkLoadFailure(): void {
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  if (offline) {
    toast(CHUNK_OFFLINE_MESSAGE, { duration: 8000 });
    return;
  }
  toast(CHUNK_RELOAD_MESSAGE, {
    duration: 10000,
    action: { label: "Reload", onClick: () => window.location.reload() },
  });
}
