"use client";

import { useSyncExternalStore } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { SOUND_MUTED_EVENT, isSoundMuted, setSoundMuted } from "@/lib/sound-pref";

function subscribe(onChange: () => void): () => void {
  window.addEventListener(SOUND_MUTED_EVENT, onChange);
  return () => window.removeEventListener(SOUND_MUTED_EVENT, onChange);
}

/** A306 — mute / unmute every beep and voice cue of the session. */
export function SoundToggle({ className = "" }: { className?: string }) {
  const muted = useSyncExternalStore(subscribe, isSoundMuted, () => false);

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        setSoundMuted(!muted);
      }}
      aria-pressed={muted}
      aria-label={muted ? "Turn sound on" : "Mute sound"}
      className={`flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg border transition-colors active:scale-95 motion-reduce:active:scale-100 ${
        muted
          ? "border-warning/40 bg-warning/10 text-warning"
          : "border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50"
      } ${className}`}
    >
      {muted ? <VolumeX className="size-5" /> : <Volume2 className="size-5" />}
    </button>
  );
}
