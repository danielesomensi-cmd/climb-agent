"use client";

// A-COACH-V1a — Coach chat. Conversational layer over the deterministic
// engine: the coach sees profile, plan, today's session and recent logs, but
// only suggests — every actual change goes through the existing app actions.
// No streaming in v1a (deferred to A-COACH-V1b): the wait is made explicit
// with a "Coach is thinking…" indicator.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import {
  ApiError,
  applyEvents,
  coachAdhocSession,
  coachChat,
  createCustomSession,
  getCoachHistory,
  getCoachSuggestions,
  getWeek,
  type AdhocSessionPreview,
  type CoachMessage,
} from "@/lib/api";
import { buildGuidedStateFromExercises, saveGuidedState } from "@/lib/guided-session-utils";
import { shouldRouteToAdhoc } from "@/lib/adhoc-gate";

const PAGE_SIZE = 50;

/** Local (not UTC) YYYY-MM-DD — matches how the app dates "today" elsewhere. */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// B282/B306 — gate logic lives in lib/adhoc-gate.ts (unit-tested); B306 adds
// short-follow-up routing ("Si", "Crea!") when the recent turns are
// adhoc-flavored, closing the 2026-07-28 fake-build-confirmation failure.

// B306 — history rows persist the composed payload as `adhoc_session`
// (snake_case from the API); the renderer keys off `adhocSession`.
function hydrateAdhocCard(msg: CoachMessage): CoachMessage {
  return msg.adhoc_session ? { ...msg, adhocSession: msg.adhoc_session } : msg;
}

function exerciseLine(ex: AdhocSessionPreview["exercises"][number]): string {
  const parts: string[] = [];
  const sets = ex.sets ?? 1;
  if (ex.reps != null && ex.reps > 0) parts.push(`${sets}×${ex.reps}`);
  else if (ex.work_seconds != null && ex.work_seconds > 0) parts.push(`${sets}×${ex.work_seconds}s`);
  else parts.push(`${sets} sets`);
  if (ex.load_kg > 0) parts.push(`${ex.load_kg} kg`);
  return parts.join(" · ");
}

function AdhocSessionCard({
  session,
  onAddAndRun,
  busy,
}: {
  session: AdhocSessionPreview;
  onAddAndRun: (s: AdhocSessionPreview) => void;
  busy: boolean;
}) {
  return (
    <div className="max-w-[92%] space-y-3 rounded-2xl rounded-bl-md border border-primary/30 bg-muted/50 px-4 py-3 text-sm">
      <div>
        <p className="font-semibold">{session.name}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          ~{session.estimated_duration_minutes} min · load {session.estimated_load_score}
        </p>
      </div>
      {session.effort_band && (
        <p className="text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground/80">This phase:</span> {session.effort_band}
        </p>
      )}
      <ul className="space-y-1.5">
        {session.exercises.map((ex, i) => (
          <li key={`${ex.exercise_id}-${i}`} className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate">{ex.name}</span>
            <span className="shrink-0 tabular-nums text-xs text-muted-foreground">{exerciseLine(ex)}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => onAddAndRun(session)}
        disabled={busy}
        className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-40"
      >
        {busy ? "Adding…" : "Add to today & run"}
      </button>
      <p className="text-[10px] leading-tight text-muted-foreground">
        Adds an off-plan session to today — never changes your planned training.
      </p>
    </div>
  );
}

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

function MessageBubble({
  msg,
  onAddAndRun,
  busy,
}: {
  msg: CoachMessage;
  onAddAndRun: (s: AdhocSessionPreview) => void;
  busy: boolean;
}) {
  const isUser = msg.role === "user";
  // A243 — an assistant turn carrying a composed session renders as a card.
  if (msg.adhocSession) {
    return (
      <div className="flex justify-start">
        <AdhocSessionCard session={msg.adhocSession} onAddAndRun={onAddAndRun} busy={busy} />
      </div>
    );
  }
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
  const router = useRouter();
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
        setMessages(data.messages.map(hydrateAdhocCard));
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
      setMessages((prev) => [...data.messages.map(hydrateAdhocCard), ...prev]);
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
        // A243/B306: route plausibly-adhoc turns (and short follow-ups in an
        // adhoc-flavored conversation) to the deterministic composer. The
        // backend is the authority — {adhoc:false} means fall back to chat.
        const gateContext = messages.map((m) => ({
          content: m.content,
          hasAdhocCard: Boolean(m.adhocSession),
        }));
        if (shouldRouteToAdhoc(text, gateContext)) {
          const res = await coachAdhocSession(text);
          if (res.adhoc && res.session) {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: res.summary ?? "", adhocSession: res.session },
            ]);
            return;
          }
        }
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
    [sending, messages]
  );

  const send = useCallback(() => sendText(input), [input, sendText]);

  // A243: persist-on-accept + insert into today + open the Phase-1 player.
  const [addingAdhoc, setAddingAdhoc] = useState(false);
  const handleAddAndRun = useCallback(
    async (session: AdhocSessionPreview) => {
      if (addingAdhoc) return;
      setAddingAdhoc(true);
      setError(null);
      try {
        const created = await createCustomSession({
          name: session.name,
          tags: session.tags,
          exercises: session.exercises,
        });
        const today = localToday();
        const week = await getWeek(0);
        if (!week.week_plan) {
          throw new Error("No current week plan — open This Week once, then retry.");
        }
        await applyEvents({
          events: [
            {
              event_type: "add_custom_session",
              custom_session_id: created.id,
              target_date: today,
              slot: "evening",
            },
          ],
          week_plan: week.week_plan,
        });
        // B283: run through the REAL guided player (progress, navigation,
        // cues, loads) — the minimal A211 playback page is retired.
        const guidedState = buildGuidedStateFromExercises(
          `custom_${created.id}`,
          created.name,
          today,
          (created.exercises ?? []) as unknown as Array<Record<string, unknown>>,
        );
        if (guidedState) saveGuidedState(guidedState);
        router.push(`/guided/${today}/custom_${created.id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : friendlyError(e));
        setAddingAdhoc(false);
      }
    },
    [addingAdhoc, router]
  );

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
            <MessageBubble
              key={m.id ?? `${m.created_at ?? "local"}-${i}`}
              msg={m}
              onAddAndRun={handleAddAndRun}
              busy={addingAdhoc}
            />
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
