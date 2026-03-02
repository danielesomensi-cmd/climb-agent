const STORAGE_KEY = "climb_voice_cues";

export function isVoiceCuesEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === null ? true : stored === "true";
}

export function setVoiceCuesEnabled(enabled: boolean): void {
  localStorage.setItem(STORAGE_KEY, String(enabled));
}

function speak(text: string): void {
  try {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.volume = 0.8;
    speechSynthesis.speak(utterance);
  } catch {
    /* silent — not all browsers support Web Speech API */
  }
}

const PHASE_CUES: Record<string, string> = {
  work: "Go",
  set_rest: "Rest",
  rep_rest: "Hold",
  complete: "Done",
  get_ready: "Get ready",
};

export function speakPhaseTransition(phase: string): void {
  if (!isVoiceCuesEnabled()) return;
  const cue = PHASE_CUES[phase];
  if (cue) speak(cue);
}
