const STORAGE_KEY = "climb_voice_cues";

export function isVoiceCuesEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === null ? true : stored === "true";
}

export function setVoiceCuesEnabled(enabled: boolean): void {
  localStorage.setItem(STORAGE_KEY, String(enabled));
}

function speak(text: string, lang?: string): void {
  try {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.volume = 0.8;
    if (lang) utterance.lang = lang;
    speechSynthesis.speak(utterance);
  } catch {
    /* silent — not all browsers support Web Speech API */
  }
}

const PHASE_CUES: Record<string, string> = {
  work: "Go",
  rest: "Rest",
  set_rest: "Rest",
  rep_rest: "Hold",
  complete: "Done",
  get_ready: "Get ready",
};

// ---------------------------------------------------------------------------
// Voice encouragement pool — ~30% chance to replace "Go" on work phase
// ---------------------------------------------------------------------------

const ENCOURAGEMENT_POOL = [
  { text: "Alé duro!", lang: "it-IT" },
  { text: "Forza!", lang: "it-IT" },
  { text: "Dai che ce la fai!", lang: "it-IT" },
  { text: "Venga!", lang: "es-ES" },
  { text: "Let's go!", lang: "en-US" },
  { text: "Send it!", lang: "en-US" },
  { text: "You got this!", lang: "en-US" },
  { text: "Crush!", lang: "en-US" },
] as const;

export function speakPhaseTransition(phase: string): void {
  if (!isVoiceCuesEnabled()) return;

  // Work phase: 30% chance to use a random encouragement phrase
  if (phase === "work" && Math.random() < 0.3) {
    const phrase = ENCOURAGEMENT_POOL[Math.floor(Math.random() * ENCOURAGEMENT_POOL.length)];
    speak(phrase.text, phrase.lang);
    return;
  }

  const cue = PHASE_CUES[phase];
  if (cue) speak(cue);
}
