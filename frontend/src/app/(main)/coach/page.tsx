"use client";

// A-COACH-V1a — Coach chat. Conversational layer over the deterministic
// engine: the coach sees profile, plan, today's session and recent logs, but
// only suggests — every actual change goes through the existing app actions.
// No streaming in v1a (deferred to A-COACH-V1b): the wait is made explicit
// with a "Coach is thinking…" indicator.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { AlertTriangle } from "lucide-react";
import { TopBar } from "@/components/layout/top-bar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ApiError,
  applyEvents,
  checkKeyConflicts,
  coachAdhocSession,
  coachChat,
  createCustomSession,
  deleteCustomSession,
  getCoachHistory,
  getCoachSuggestions,
  getCustomSession,
  getWeek,
  type AdhocSessionPreview,
  type CoachMessage,
} from "@/lib/api";
import { MarkdownLite } from "@/components/shared/markdown-lite";
import { buildGuidedStateFromExercises, saveGuidedState } from "@/lib/guided-session-utils";
import { shouldRouteToAdhoc } from "@/lib/adhoc-gate";
import { findDay, firstFreeSlot } from "@/lib/day-slots";
import { blockingConflicts, localToday } from "@/lib/key-sessions";
import { boulderGradeSystemOf } from "@/lib/gradeUtils";
import { previewLimitTarget } from "@/lib/adhoc-preview";
import {
  adhocCardDate,
  dayDividers,
  dayLabel,
  dropFailedUserTurn,
  isRetryableStatus,
  isStaleAdhocCard,
  requestBefore,
} from "@/lib/coach-chat";
import { useUserState } from "@/lib/hooks/queries/use-user-state";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 50;

const DISCLAIMER = "AI coach — suggestions only, it never changes your plan. Not medical advice.";

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
  createdAt,
  onAddAndRun,
  onAskAgain,
  busy,
}: {
  session: AdhocSessionPreview;
  createdAt?: string;
  onAddAndRun: (s: AdhocSessionPreview) => void;
  /** Stale cards only: re-sends the original request (a NEW composition for today). */
  onAskAgain: (() => void) | null;
  busy: boolean;
}) {
  const authReady = useAuth().isLoaded;
  const gradeSystem = boulderGradeSystemOf(useUserState(authReady).data);
  const today = localToday();
  // A310 — a card composed on another day keeps that day's loads and key
  // check: adding it to today would play the wrong numbers, so it has no add CTA.
  const stale = isStaleAdhocCard(session.resolved_for_date, createdAt, today);
  const builtFor = adhocCardDate(session.resolved_for_date, createdAt);
  return (
    <div
      className={`max-w-[92%] space-y-3 rounded-xl rounded-bl-md border bg-card px-4 py-3 text-sm shadow-sm ${
        stale ? "border-border opacity-80" : "border-primary/30"
      }`}
    >
      <div>
        <p className="font-semibold">{session.name}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          ~{session.estimated_duration_minutes} min · load {session.estimated_load_score}
          {stale && builtFor && ` · Composed for ${dayLabel(builtFor, today).replace(/^Yesterday$/, "yesterday")}`}
        </p>
      </div>
      {session.key_warnings && session.key_warnings.length > 0 && (
        <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning-muted px-3 py-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <ul className="space-y-1">
            {session.key_warnings.map((w, i) => (
              <li key={`${w.code}-${i}`} className="text-sm text-warning">{w.message}</li>
            ))}
          </ul>
        </div>
      )}
      {session.effort_band && (
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">This phase:</span> {session.effort_band}
        </p>
      )}
      <ul className="space-y-2">
        {session.exercises.map((ex, i) => (
          <li key={`${ex.exercise_id}-${i}`}>
            <p className="text-sm font-medium">{ex.name}</p>
            <p className="text-xs tabular-nums text-fg-secondary">
              {[exerciseLine(ex), previewLimitTarget(ex, session.resolved_for_date, today, gradeSystem)]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </li>
        ))}
      </ul>
      {stale ? (
        onAskAgain && (
          <button
            type="button"
            onClick={onAskAgain}
            disabled={busy}
            className="min-h-[44px] w-full rounded-xl border border-border px-4 py-3 text-sm font-medium text-foreground hover:border-primary disabled:opacity-40"
          >
            Ask again for today
          </button>
        )
      ) : (
        <>
          <button
            type="button"
            onClick={() => onAddAndRun(session)}
            disabled={busy}
            className="min-h-[44px] w-full rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            {busy ? "Adding…" : "Add to today & run"}
          </button>
          <p className="text-xs leading-snug text-muted-foreground">
            Adds an off-plan session to today — never changes your planned training. Not medical advice.
          </p>
        </>
      )}
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
  onAskAgain,
  busy,
}: {
  msg: CoachMessage;
  onAddAndRun: (s: AdhocSessionPreview) => void;
  onAskAgain: (() => void) | null;
  busy: boolean;
}) {
  const isUser = msg.role === "user";
  // A243 — an assistant turn carrying a composed session renders as a card.
  if (msg.adhocSession) {
    return (
      <div className="flex justify-start">
        <AdhocSessionCard
          session={msg.adhocSession}
          createdAt={msg.created_at}
          onAddAndRun={onAddAndRun}
          onAskAgain={onAskAgain}
          busy={busy}
        />
      </div>
    );
  }
  // A286 — il turno dell'utente è testo puro (pre-wrap); quello del coach è
  // markdown e va renderizzato, altrimenti restano a video ## e ** grezzi.
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "whitespace-pre-wrap rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-border bg-card text-foreground shadow-sm"
        }`}
      >
        {isUser ? msg.content : <MarkdownLite text={msg.content} />}
      </div>
    </div>
  );
}

function DayDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-2" role="separator" aria-label={label}>
      <span className="h-px flex-1 bg-border-subtle" />
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border-subtle" />
    </div>
  );
}

function ThinkingIndicator({ label }: { label: string }) {
  return (
    <div className="flex justify-start" role="status">
      <div className="flex items-center gap-2 rounded-xl rounded-bl-md border border-border bg-card px-4 py-3">
        <span className="h-2 w-2 animate-pulse rounded-full bg-primary" aria-hidden="true" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-3 pt-4" aria-label="Loading conversation" role="status">
      <div className="flex justify-end">
        <div className="h-10 w-2/3 animate-pulse rounded-xl bg-muted" />
      </div>
      <div className="flex justify-start">
        <div className="h-16 w-2/3 animate-pulse rounded-xl bg-muted" />
      </div>
      <div className="flex justify-end">
        <div className="h-10 w-2/3 animate-pulse rounded-xl bg-muted" />
      </div>
    </div>
  );
}

interface ChatError {
  message: string;
  /** Set only for a failed send that can succeed on a second try. */
  retryText?: string;
}

export default function CoachPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [sending, setSending] = useState(false);
  const [thinkingAdhoc, setThinkingAdhoc] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState<ChatError | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const coordsRef = useRef<{ lat: number; lon: number } | null>(null);

  const pageRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getCoachHistory(PAGE_SIZE)
      .then((data) => {
        setMessages(data.messages.map(hydrateAdhocCard));
        setHasMore(data.has_more);
      })
      .catch((e) => setError({ message: friendlyError(e) }))
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

  // A310 — the sticky composer's real height (chips appear and go, the
  // textarea grows) as --composer-h, so the auto-scroll stops above it.
  useEffect(() => {
    const composer = composerRef.current;
    const page = pageRef.current;
    if (!composer || !page || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      page.style.setProperty("--composer-h", `${composer.offsetHeight}px`);
    });
    ro.observe(composer);
    return () => ro.disconnect();
  }, []);

  // Keep the view pinned to the latest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending, error]);

  const loadEarlier = useCallback(async () => {
    const oldest = messages[0]?.created_at;
    if (!oldest || loadingEarlier) return;
    setLoadingEarlier(true);
    try {
      const data = await getCoachHistory(PAGE_SIZE, oldest);
      setMessages((prev) => [...data.messages.map(hydrateAdhocCard), ...prev]);
      setHasMore(data.has_more);
    } catch (e) {
      setError({ message: friendlyError(e) });
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
      // A243/B306: route plausibly-adhoc turns (and short follow-ups in an
      // adhoc-flavored conversation) to the deterministic composer. The
      // backend is the authority — {adhoc:false} means fall back to chat.
      const gateContext = messages.map((m) => ({
        content: m.content,
        hasAdhocCard: Boolean(m.adhocSession),
      }));
      const adhocTurn = shouldRouteToAdhoc(text, gateContext);
      setThinkingAdhoc(adhocTurn);
      setSending(true);
      try {
        if (adhocTurn) {
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
        // A310 — the question goes back into the composer (nothing to retype
        // on a phone) and its unanswered bubble goes away, so a Retry never
        // shows it twice.
        setMessages((prev) => dropFailedUserTurn(prev, text));
        setInput(text);
        const status = e instanceof ApiError ? e.status : undefined;
        setError({
          message: friendlyError(e),
          retryText: isRetryableStatus(status) ? text : undefined,
        });
      } finally {
        setSending(false);
        inputRef.current?.focus();
      }
    },
    [sending, messages]
  );

  const send = useCallback(() => sendText(input), [input, sendText]);

  // A310 — the key-session conflict confirm is an in-app AlertDialog (was
  // window.confirm); handleAddAndRun awaits the user's answer.
  const [conflictPrompt, setConflictPrompt] = useState<{
    messages: string[];
    resolve: (ok: boolean) => void;
  } | null>(null);
  const askConflictConfirm = useCallback(
    (msgs: string[]) =>
      new Promise<boolean>((resolve) => setConflictPrompt({ messages: msgs, resolve })),
    []
  );
  const settleConflict = useCallback(
    (ok: boolean) => {
      conflictPrompt?.resolve(ok);
      setConflictPrompt(null);
    },
    [conflictPrompt]
  );

  // A243: persist-on-accept + insert into today + open the Phase-1 player.
  const [addingAdhoc, setAddingAdhoc] = useState(false);
  const handleAddAndRun = useCallback(
    async (session: AdhocSessionPreview) => {
      if (addingAdhoc) return;
      setAddingAdhoc(true);
      setError(null);
      try {
        const today = localToday();
        const week = await getWeek(0);
        if (!week.week_plan) {
          throw new Error("No current week plan — open This Week once, then retry.");
        }
        // B309: resolve a FREE slot before creating anything. The CTA used to
        // hardcode "evening"; on a day whose evening was already planned the
        // insert 422'd ("Slot 'evening' already occupied") AFTER the custom
        // session had been persisted, leaving it orphaned and invisible.
        const day = findDay(week.week_plan, today);
        if (!day) {
          throw new Error("Today isn't in the current week plan — open This Week once, then retry.");
        }
        const slot = firstFreeSlot(day);
        if (!slot) {
          throw new Error(
            "Today is fully booked (morning, lunch and evening). Free a slot from This Week, then retry."
          );
        }
        // A294: dry run BEFORE creating anything (no orphan customs) — a
        // session that would take a key session's place asks for a confirm.
        const conflicts = blockingConflicts(
          await checkKeyConflicts({
            events: [{ event_type: "add_custom_session", custom_session_id: "preview", target_date: today, slot }],
            week_plan: week.week_plan,
            custom_session_payload: { id: "preview", name: session.name, exercises: session.exercises },
          }),
        );
        if (conflicts.length > 0 && !(await askConflictConfirm(conflicts.map((c) => c.message)))) {
          setAddingAdhoc(false);
          return;
        }
        const created = await createCustomSession({
          name: session.name,
          tags: session.tags,
          exercises: session.exercises,
        });
        try {
          await applyEvents({
            events: [
              {
                event_type: "add_custom_session",
                custom_session_id: created.id,
                target_date: today,
                slot,
              },
            ],
            week_plan: week.week_plan,
          });
        } catch (e) {
          // Never leave a session saved but unplanned — that is exactly the
          // state that made the coach look like it had silently done nothing.
          await deleteCustomSession(created.id).catch(() => {});
          throw e;
        }
        // B371: the week moved on the server (the GET above may have
        // regenerated it, the add moved its revision) — a cached copy left
        // behind would make the next write from /today or /week a false 409.
        void qc.invalidateQueries({ queryKey: queryKeys.weekAll });
        // A299: play what the read of TODAY says — anchored loads, ladder
        // doses, measures and the limit target recomputed by the same
        // functions as /week and the custom player (the create response is
        // the stored rows, without any read-time value). Fallback: the rows.
        const played = await getCustomSession(created.id, today).catch(() => created);
        // B283: run through the REAL guided player (progress, navigation,
        // cues, loads) — the minimal A211 playback page is retired.
        const guidedState = buildGuidedStateFromExercises(
          `custom_${created.id}`,
          created.name,
          today,
          (played.exercises ?? created.exercises ?? []) as unknown as Array<Record<string, unknown>>,
        );
        if (guidedState) saveGuidedState(guidedState);
        router.push(`/guided/${today}/custom_${created.id}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : friendlyError(e);
        // B309: the engine's raw slot-conflict text is not actionable for a
        // user who never picked a slot — mirror what /week and /today show.
        setError({
          message: msg.includes("already occupied")
            ? "Today is fully booked. Free a slot from This Week, then retry."
            : msg,
        });
        setAddingAdhoc(false);
      }
    },
    [addingAdhoc, router, qc, askConflictConfirm]
  );

  const today = localToday();
  const dividers = dayDividers(messages, today);
  const isEmpty = !loadingHistory && messages.length === 0;

  return (
    // A286 — 100dvh: con 100vh su iOS la barra URL mangiava l'ultima riga.
    // A310 — the height left above the nav is the --nav-h token, not 5rem.
    <div ref={pageRef} className="flex min-h-[calc(100dvh-var(--nav-h))] flex-col">
      <TopBar title="Coach" compact />

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-4">
        <div className="flex-1 space-y-3">
          {loadingHistory && <HistorySkeleton />}

          {!loadingHistory && hasMore && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={loadEarlier}
                disabled={loadingEarlier}
                className="min-h-[44px] rounded-full border border-border px-4 text-xs text-muted-foreground hover:text-foreground"
              >
                {loadingEarlier ? "Loading…" : "Load earlier messages"}
              </button>
            </div>
          )}

          {isEmpty && (
            <div className="space-y-4 pt-8">
              <div className="space-y-2 text-center">
                <p className="text-lg font-semibold">Ask your coach anything</p>
                <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                  The coach knows your plan, today&apos;s session, and your
                  recent training.
                  {suggestions.length === 0 && (
                    <>
                      {" "}Try: &ldquo;I don&apos;t feel like going to the gym
                      today — what can I do instead?&rdquo;
                    </>
                  )}
                </p>
              </div>
              {suggestions.length > 0 && (
                <div className="space-y-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => sendText(s)}
                      disabled={sending}
                      className="min-h-[48px] w-full rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-foreground transition-colors hover:border-primary disabled:opacity-40"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
              <p className="text-center text-xs text-muted-foreground">{DISCLAIMER}</p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={m.id ?? `${m.created_at ?? "local"}-${i}`} className="space-y-3">
              {dividers[i] && <DayDivider label={dividers[i]} />}
              <MessageBubble
                msg={m}
                onAddAndRun={handleAddAndRun}
                onAskAgain={(() => {
                  const request = m.adhocSession ? requestBefore(messages, i) : null;
                  return request ? () => sendText(request) : null;
                })()}
                busy={addingAdhoc}
              />
            </div>
          ))}

          {sending && (
            <ThinkingIndicator label={thinkingAdhoc ? "Building your session…" : "Coach is thinking…"} />
          )}

          {error && (
            <div className="flex justify-start">
              <div
                role="alert"
                className="max-w-[85%] space-y-2 rounded-xl rounded-bl-md border border-danger/40 bg-danger-muted px-4 py-2.5 text-sm text-danger"
              >
                <p>{error.message}</p>
                {error.retryText && (
                  <button
                    type="button"
                    onClick={() => error.retryText && sendText(error.retryText)}
                    disabled={sending}
                    className="min-h-[44px] rounded-lg border border-danger/40 px-4 text-sm font-medium text-foreground hover:bg-danger/10 disabled:opacity-40"
                  >
                    Retry
                  </button>
                )}
              </div>
            </div>
          )}

          {/* A310 — scroll margin = nav + composer: scrolled "to the end" the
              newest reply stops above the sticky composer, not under it. */}
          <div
            ref={bottomRef}
            className="scroll-mb-[calc(var(--nav-h)+var(--composer-h,9rem))]"
          />
        </div>

        {/* Composer — sticky above the bottom nav.
            A286: l'offset era `bottom-20` (5rem) a occhio; la bottom nav è alta
            3.5rem + safe-area, quindi su iPhone col notch il composer finiva
            sotto la nav. A310: l'offset è il token --nav-h, e lo sfondo è lo
            stesso della nav, così composer e nav si leggono come una sola barra. */}
        <div
          ref={composerRef}
          className="sticky bottom-[var(--nav-h)] -mx-4 mt-3 border-t border-border-subtle bg-background/95 px-4 pb-2 pt-2 backdrop-blur supports-[backdrop-filter]:bg-background/85"
        >
          {/* A-COACH-V1b: suggested-question chips — shown while composing.
              A310: in the empty state they are the full-width list above. */}
          {suggestions.length > 0 && messages.length > 0 && !input.trim() && !sending && (
            <div className="scrollbar-none -mx-1 mb-2 flex gap-2 overflow-x-auto px-1 pb-0.5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => sendText(s)}
                  className="min-h-[44px] shrink-0 rounded-full border border-border bg-muted/40 px-4 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
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
              aria-label="Message the coach"
              /* A286 — text-base (16px): sotto i 16px iOS zooma al focus e non torna indietro. */
              className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-border bg-muted/50 px-4 py-2.5 text-base outline-none placeholder:text-muted-foreground focus:border-primary"
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
        </div>
      </main>

      <AlertDialog open={!!conflictPrompt} onOpenChange={(open) => { if (!open) settleConflict(false); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Add it anyway?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                {conflictPrompt?.messages.map((m, i) => (
                  <p key={i}>{m}</p>
                ))}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => settleConflict(true)}>Add anyway</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
