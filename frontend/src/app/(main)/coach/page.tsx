"use client";

// A-COACH-V1a — Coach chat. Conversational layer over the deterministic
// engine: the coach sees profile, plan, today's session and recent logs, but
// only suggests — every actual change goes through the existing app actions.
// No streaming in v1a (deferred to A-COACH-V1b): the wait is made explicit
// with a "Coach is thinking…" indicator.

import { useCallback, useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/layout/top-bar";
import {
  ApiError,
  coachChat,
  getCoachHistory,
  getCoachSuggestions,
  type CoachMessage,
} from "@/lib/api";

const PAGE_SIZE = 50;

function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 429)
      return "You've reached today's coach limit — back tomorrow!";
    if (e.status === 402) return e.message;
    if (e.status === 500 || e.status === 502)
      return "The coach is temporarily unavailable — try again in a minute.";
  }
  return "Something went wrong — try again.";
}

function MessageBubble({ msg }: { msg: CoachMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md bg-muted text-foreground"
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-muted px-4 py-3">
        <span className="flex gap-1">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        <span className="text-xs text-muted-foreground">
          Coach is thinking…
        </span>
      </div>
    </div>
  );
}

export default function CoachPage() {
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const coordsRef = useRef<{ lat: number; lon: number } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getCoachHistory(PAGE_SIZE)
      .then((data) => {
        setMessages(data.messages);
        setHasMore(data.has_more);
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoadingHistory(false));
  }, []);

  // A-COACH-V1b: suggested-question chips (deterministic, no LLM call).
  useEffect(() => {
    getCoachSuggestions()
      .then((data) => setSuggestions(data.suggestions))
      .catch(() => setSuggestions([])); // chips are optional — fail silent
  }, []);

  // A-COACH-V1b: current location → weather in the coach context. Same
  // permission the /today weather card already uses; denied → silently off.
  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        coordsRef.current = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
        };
      },
      () => {},
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 15 * 60 * 1000 }
    );
  }, []);

  // Keep the view pinned to the latest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending]);

  const loadEarlier = useCallback(async () => {
    const oldest = messages[0]?.created_at;
    if (!oldest || loadingEarlier) return;
    setLoadingEarlier(true);
    try {
      const data = await getCoachHistory(PAGE_SIZE, oldest);
      setMessages((prev) => [...data.messages, ...prev]);
      setHasMore(data.has_more);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoadingEarlier(false);
    }
  }, [messages, loadingEarlier]);

  const sendText = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || sending) return;
      setError(null);
      setInput("");
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setSending(true);
      try {
        const { reply } = await coachChat(text, coordsRef.current);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: reply },
        ]);
      } catch (e) {
        setError(friendlyError(e));
      } finally {
        setSending(false);
        inputRef.current?.focus();
      }
    },
    [sending]
  );

  const send = useCallback(() => sendText(input), [input, sendText]);

  return (
    <div className="flex min-h-[calc(100vh-5rem)] flex-col">
      <TopBar title="Coach" subtitle="Your AI climbing coach" />

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-4">
        <div className="flex-1 space-y-3">
          {loadingHistory && (
            <p className="pt-8 text-center text-sm text-muted-foreground">
              Loading conversation…
            </p>
          )}

          {!loadingHistory && hasMore && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={loadEarlier}
                disabled={loadingEarlier}
                className="rounded-full border border-border px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                {loadingEarlier ? "Loading…" : "Load earlier messages"}
              </button>
            </div>
          )}

          {!loadingHistory && messages.length === 0 && (
            <div className="space-y-3 pt-8 text-center">
              <p className="text-lg font-semibold">Ask your coach anything</p>
              <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                The coach knows your plan, today&apos;s session, and your
                recent training. Try: &ldquo;I don&apos;t feel like going to
                the gym today — what can I do instead?&rdquo;
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <MessageBubble key={m.id ?? `${m.created_at ?? "local"}-${i}`} msg={m} />
          ))}

          {sending && <ThinkingIndicator />}

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Composer + disclaimer — sticky above the bottom nav */}
        <div className="sticky bottom-20 -mx-4 mt-3 border-t border-border bg-background/95 px-4 pb-2 pt-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          {/* A-COACH-V1b: suggested-question chips — shown while composing */}
          {suggestions.length > 0 && !input.trim() && !sending && (
            <div className="scrollbar-none -mx-1 mb-2 flex gap-2 overflow-x-auto px-1 pb-0.5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => sendText(s)}
                  className="shrink-0 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              maxLength={4000}
              placeholder="Ask your coach…"
              className="max-h-32 min-h-[44px] flex-1 resize-none rounded-2xl border border-border bg-muted/50 px-4 py-2.5 text-sm outline-none placeholder:text-muted-foreground focus:border-primary"
            />
            <button
              type="button"
              onClick={send}
              disabled={!input.trim() || sending}
              aria-label="Send"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 12h14M13 6l6 6-6 6"
                />
              </svg>
            </button>
          </div>
          <p className="pt-2 text-center text-[10px] leading-tight text-muted-foreground">
            AI coach — suggestions only, it never changes your plan. Not
            medical advice.
          </p>
        </div>
      </main>
    </div>
  );
}
