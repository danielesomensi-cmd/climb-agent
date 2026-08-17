"use client";

import { toast } from "sonner";
import {
  ApiError,
  NETWORK_ERROR_STATUS,
  finishOutdoorSession,
  postFeedback,
  postOutdoorLog,
  logFreeClimb,
} from "@/lib/api";
import { getKeyPrefix } from "@/lib/guided-session-utils";

/**
 * A245 B-4 (F4, F5) — one durable queue for offline writes.
 *
 * Before this, `handleFeedbackSubmit` swallowed every error with
 * `catch { /* Non-critical *\/ }` and `logFreeClimb` only console.error'd: the
 * user filled in feedback in the gym, it vanished, and progression silently
 * drifted. The guided flow already had a localStorage retry queue
 * (`feedback_pending`) — this generalises that proven pattern instead of
 * inventing a second one.
 *
 * SCOPE (approved, A245 Phase B design note). Only APPEND-ONLY, SELF-CONSISTENT
 * writes belong here. Done/Skip deliberately does NOT: `/replanner/events`
 * ships the entire week plan and the backend persists it wholesale, so
 * replaying a snapshot captured hours earlier would overwrite everything that
 * happened in between — the F6 lost-update, but unbounded in time — and could
 * violate the past-session immutability invariant. Offline Done/Skip fails
 * loudly instead.
 */

const STORAGE_KEY_BASE = "climb-agent-outbox-v1";

/** Entries older than this are dropped — but never silently (see flush). */
const MAX_AGE_MS = 72 * 60 * 60 * 1000;

/** Same reasoning as the persisted query cache: never risk QuotaExceededError. */
const MAX_BYTES = 1_000_000;

/**
 * B336 — `outdoor_finish` closes an outdoor session that was STARTED online
 * (so the server id in the payload is real and durable) but could not be
 * finished, because the signal went at the crag before the last route.
 *
 * The A245 note below excluded it on the grounds that the finish "needs a live
 * server id". That is true of a session which never reached the server — and
 * that case is now handled by starting a LOCAL session instead, which finishes
 * through `outdoor_log`. Where an id already exists, replaying the finish is
 * the correct move and the only one that also clears the active session
 * server-side; queuing a plain `outdoor_log` would write the log and leave the
 * active session dangling, to be "restored" days later.
 */
export type OutboxKind = "feedback" | "outdoor_log" | "free_climb" | "outdoor_finish";

export interface OutboxEntry {
  id: string;
  kind: OutboxKind;
  payload: Record<string, unknown>;
  createdAt: number;
  attempts: number;
}

/** Scoped per user, for the same reason the query cache is (see query-persist). */
function storageKey(): string {
  return `${STORAGE_KEY_BASE}-${getKeyPrefix()}`;
}

function read(): OutboxEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(storageKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as OutboxEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: OutboxEntry[]): boolean {
  try {
    const payload = JSON.stringify(entries);
    if (payload.length > MAX_BYTES) {
      console.warn(`[outbox] ${payload.length}B over the ${MAX_BYTES}B guard — write refused`);
      return false;
    }
    window.localStorage.setItem(storageKey(), payload);
    return true;
  } catch (err) {
    console.warn("[outbox] write failed:", err);
    return false;
  }
}

function newId(): string {
  // crypto.randomUUID is available in every browser that can run this PWA.
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * Queue a write for later. Returns false if it could not be stored, so the
 * caller can tell the user rather than pretend it is safe.
 */
export function enqueue(kind: OutboxKind, payload: Record<string, unknown>): boolean {
  if (typeof window === "undefined") return false;
  const entries = read();
  entries.push({ id: newId(), kind, payload, createdAt: Date.now(), attempts: 0 });
  return write(entries);
}

export function pendingCount(): number {
  return read().length;
}

/** Dispatch one entry to its endpoint. */
async function send(entry: OutboxEntry): Promise<void> {
  switch (entry.kind) {
    case "feedback":
      await postFeedback(entry.payload as never);
      return;
    case "outdoor_log":
      await postOutdoorLog(entry.payload as never);
      return;
    case "free_climb": {
      const { session_id: sessionId, ...climb } = entry.payload as {
        session_id: string;
      } & Record<string, unknown>;
      await logFreeClimb(sessionId, climb as never);
      return;
    }
    case "outdoor_finish": {
      const { session_id: sessionId, ...body } = entry.payload as {
        session_id: string;
      } & Record<string, unknown>;
      await finishOutdoorSession(sessionId, body as never);
      return;
    }
  }
}

/**
 * A failure that will never succeed on retry (bad request, gone, forbidden)
 * must not clog the queue forever. Network errors, timeouts, throttling and
 * server faults must be retried.
 */
function isPermanent(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === NETWORK_ERROR_STATUS) return false;
  if (err.status === 408 || err.status === 429) return false;
  return err.status >= 400 && err.status < 500;
}

/**
 * B336 — a permanent failure that means "already done", not "rejected".
 *
 * `finishOutdoorSession` 404s once the active session is gone, and the most
 * likely way for that to happen is that the original call SUCCEEDED and only
 * its response was lost. The log is already written; telling the user their
 * entry "was rejected by the server" would be both alarming and false.
 */
function isAlreadyApplied(entry: OutboxEntry, err: unknown): boolean {
  return (
    entry.kind === "outdoor_finish" &&
    err instanceof ApiError &&
    err.status === 404
  );
}

let flushing = false;

/**
 * Drain the queue. Safe to call repeatedly; concurrent calls are collapsed.
 * Entries are processed in order and a retryable failure stops the pass —
 * order matters (a climb must not overtake the session it belongs to) and
 * hammering a dead network wastes battery.
 */
export async function flush(): Promise<{ sent: number; remaining: number }> {
  if (typeof window === "undefined" || flushing) {
    return { sent: 0, remaining: pendingCount() };
  }
  flushing = true;
  try {
    let entries = read();
    if (entries.length === 0) return { sent: 0, remaining: 0 };

    const now = Date.now();
    const expired = entries.filter((e) => now - e.createdAt > MAX_AGE_MS);
    if (expired.length > 0) {
      entries = entries.filter((e) => now - e.createdAt <= MAX_AGE_MS);
      write(entries);
      // Never drop user data silently — that is the failure mode this whole
      // phase exists to remove.
      toast.error(
        `${expired.length} offline ${expired.length === 1 ? "entry" : "entries"} expired and could not be saved.`,
        { duration: 10_000 },
      );
    }

    let sent = 0;
    for (const entry of [...entries]) {
      try {
        await send(entry);
        entries = entries.filter((e) => e.id !== entry.id);
        write(entries);
        sent++;
      } catch (err) {
        if (isAlreadyApplied(entry, err)) {
          entries = entries.filter((e) => e.id !== entry.id);
          write(entries);
          sent++;
          continue;
        }
        if (isPermanent(err)) {
          entries = entries.filter((e) => e.id !== entry.id);
          write(entries);
          console.error("[outbox] dropping permanently failed entry:", entry.kind, err);
          toast.error("An offline entry was rejected by the server and could not be saved.", {
            duration: 10_000,
          });
          continue;
        }
        // Retryable: bump the counter and stop this pass.
        entry.attempts += 1;
        write(entries);
        break;
      }
    }
    return { sent, remaining: entries.length };
  } finally {
    flushing = false;
  }
}
