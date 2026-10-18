/**
 * audio-unlock.ts — Singleton AudioContext with iOS Safari PWA unlock trick.
 *
 * iOS Safari (especially in PWA / Add-to-Home-Screen mode) requires:
 * 1. AudioContext created/resumed inside a user-gesture handler
 * 2. A silent buffer played to fully "unlock" the context
 * 3. Re-resume on visibilitychange (PWA suspends on background)
 */

let _ctx: AudioContext | null = null;

/**
 * Return the shared AudioContext, creating it on first call.
 * Safe to call outside a gesture — the context will be "suspended" until
 * unlockAudio() is called inside a gesture handler.
 */
export function getAudioContext(): AudioContext {
  if (_ctx && _ctx.state !== "closed") return _ctx;

  const Ctx =
    typeof window !== "undefined"
      ? window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext
      : undefined;

  if (!Ctx) throw new Error("AudioContext not supported");

  _ctx = new Ctx();
  return _ctx;
}

/**
 * Unlock audio on iOS Safari.  MUST be called inside a user-gesture handler
 * (touchstart, click, keydown).
 *
 * - Resumes the context if suspended
 * - Plays a 1-sample silent buffer to satisfy iOS's "user played audio" gate
 */
export async function unlockAudio(): Promise<void> {
  try {
    const ctx = getAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    // Play a silent buffer — iOS needs this to fully unlock audio output
    const buffer = ctx.createBuffer(1, 1, 22050);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(0);
  } catch {
    /* silent — audio not supported or blocked */
  }
}

/**
 * B397 G4 — let the session's cues through the iPhone silent switch.
 *
 * Web Audio on iOS follows the ring/silent switch by default, so with the
 * phone on silent the end of a rest made no sound at all. The Audio Session
 * API (Safari 16.4+) can ask for the `playback` category, which plays through
 * the switch. Used ONLY while a guided session is open and its sound is on
 * (the player resets it to `auto` when it closes or is muted): `playback` may
 * also pause music another app is playing — that is the trade-off to check on
 * a device. Browsers without the API: no-op.
 */
type AudioSessionType = "auto" | "playback" | "transient" | "transient-solo" | "ambient" | "play-and-record";

export function setPlaybackAudioSession(active: boolean): void {
  if (typeof navigator === "undefined") return;
  const session = (navigator as Navigator & { audioSession?: { type: AudioSessionType } }).audioSession;
  if (!session) return;
  try {
    session.type = active ? "playback" : "auto";
  } catch {
    /* unsupported value on this engine — keep the default */
  }
}
