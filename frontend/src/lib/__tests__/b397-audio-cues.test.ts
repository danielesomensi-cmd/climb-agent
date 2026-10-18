// B397 G4 — the end of a rest you must close with a tap is hard to miss, and
// the guided session can ask iOS to play through the silent switch.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAudioContext = vi.fn();
vi.mock("@/lib/audio-unlock", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/audio-unlock")>();
  return { ...real, getAudioContext: () => getAudioContext() };
});

import { restOverCue } from "../beep";
import { setPlaybackAudioSession } from "../audio-unlock";

class MemoryStorage {
  private map = new Map<string, string>();
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

function fakeAudioContext() {
  const started: number[] = [];
  const ctx = {
    state: "running",
    currentTime: 10,
    destination: {},
    resume: vi.fn(),
    createOscillator: () => ({
      type: "",
      frequency: { value: 0 },
      connect: vi.fn(),
      start: (at: number) => started.push(at),
      stop: vi.fn(),
    }),
    createGain: () => ({
      gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
    }),
  };
  return { ctx, started };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

let storage: MemoryStorage;

beforeEach(() => {
  getAudioContext.mockReset();
  storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("window", { localStorage: storage, dispatchEvent: () => true });
});
afterEach(() => vi.unstubAllGlobals());

describe("restOverCue", () => {
  it("plays three beeps, scheduled on the audio clock", async () => {
    const { ctx, started } = fakeAudioContext();
    getAudioContext.mockReturnValue(ctx);
    vi.stubGlobal("navigator", {});

    restOverCue();
    await flush();

    expect(started.length).toBe(3);
    // Spaced on the audio timeline, not by setTimeout.
    expect(started[0]).toBeCloseTo(10);
    expect(started[1]).toBeGreaterThan(started[0]);
    expect(started[2]).toBeGreaterThan(started[1]);
  });

  it("vibrates where the platform can (Android)", () => {
    getAudioContext.mockImplementation(() => fakeAudioContext().ctx);
    const vibrate = vi.fn<(pattern: number | number[]) => boolean>(() => true);
    vi.stubGlobal("navigator", { vibrate });

    restOverCue();

    expect(vibrate).toHaveBeenCalledTimes(1);
    const pattern = vibrate.mock.calls[0][0] as number[];
    expect(Array.isArray(pattern)).toBe(true);
    expect(pattern.reduce((a, b) => a + b, 0)).toBeGreaterThan(500);
  });

  it("muted: no sound, but the vibration still comes (A306: haptics are untouched)", async () => {
    storage.setItem("climb_sound_muted", "true");
    const vibrate = vi.fn(() => true);
    vi.stubGlobal("navigator", { vibrate });

    restOverCue();
    await flush();

    expect(getAudioContext).not.toHaveBeenCalled();
    expect(vibrate).toHaveBeenCalledTimes(1);
  });

  it("no vibration API (iOS): never throws", () => {
    getAudioContext.mockImplementation(() => fakeAudioContext().ctx);
    vi.stubGlobal("navigator", {});
    expect(() => restOverCue()).not.toThrow();
  });
});

describe("setPlaybackAudioSession", () => {
  it("asks for `playback` while active and gives `auto` back", () => {
    const audioSession = { type: "auto" };
    vi.stubGlobal("navigator", { audioSession });

    setPlaybackAudioSession(true);
    expect(audioSession.type).toBe("playback");
    setPlaybackAudioSession(false);
    expect(audioSession.type).toBe("auto");
  });

  it("is a no-op where the Audio Session API does not exist", () => {
    vi.stubGlobal("navigator", {});
    expect(() => setPlaybackAudioSession(true)).not.toThrow();
  });
});
