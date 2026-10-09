// A306 — one switch silences every beep and voice cue of a session.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAudioContext = vi.fn();
vi.mock("@/lib/audio-unlock", () => ({ getAudioContext: () => getAudioContext() }));

import { beep } from "../beep";
import { SOUND_MUTED_EVENT, isSoundMuted, setSoundMuted } from "../sound-pref";
import { speakPhaseTransition } from "../voice-cues";

class MemoryStorage {
  private map = new Map<string, string>();
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

describe("sound mute", () => {
  const speak = vi.fn();
  const cancel = vi.fn();

  beforeEach(() => {
    getAudioContext.mockReset();
    speak.mockReset();
    cancel.mockReset();
    const storage = new MemoryStorage();
    const events = new EventTarget();
    const synth = { speak, cancel };
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("speechSynthesis", synth);
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} });
    vi.stubGlobal("window", {
      localStorage: storage,
      speechSynthesis: synth,
      addEventListener: events.addEventListener.bind(events),
      removeEventListener: events.removeEventListener.bind(events),
      dispatchEvent: events.dispatchEvent.bind(events),
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("is off by default and persists", () => {
    expect(isSoundMuted()).toBe(false);
    setSoundMuted(true);
    expect(isSoundMuted()).toBe(true);
    setSoundMuted(false);
    expect(isSoundMuted()).toBe(false);
  });

  it("muted: no audio context is touched by a beep", async () => {
    setSoundMuted(true);
    await beep(880, 0.2, 0.4);
    expect(getAudioContext).not.toHaveBeenCalled();
  });

  it("unmuted: the beep reaches the audio context", async () => {
    getAudioContext.mockImplementation(() => {
      throw new Error("no audio in tests");
    });
    await beep(880, 0.2, 0.4);
    expect(getAudioContext).toHaveBeenCalled();
  });

  it("muted: voice cues are silent and an ongoing utterance is cancelled", () => {
    speakPhaseTransition("rest");
    expect(speak).toHaveBeenCalledTimes(1);
    setSoundMuted(true);
    expect(cancel).toHaveBeenCalled();
    speakPhaseTransition("rest");
    expect(speak).toHaveBeenCalledTimes(1);
  });

  it("broadcasts the change so every toggle shows the same state", () => {
    const seen: boolean[] = [];
    const on = (e: Event) => seen.push((e as CustomEvent<boolean>).detail);
    window.addEventListener(SOUND_MUTED_EVENT, on);
    setSoundMuted(true);
    setSoundMuted(false);
    window.removeEventListener(SOUND_MUTED_EVENT, on);
    expect(seen).toEqual([true, false]);
  });
});
