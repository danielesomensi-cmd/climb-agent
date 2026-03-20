"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Zap, Check, X, Plus, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GradePicker } from "./grade-picker";
import { RestTimer } from "./rest-timer";
import { logFreeClimb } from "@/lib/api";

interface Climb {
  index: number;
  grade: string;
  status: string;
  attempts: number;
  style?: string;
  topped?: boolean;
  notes?: string;
  logged_at: string;
}

export interface LoggedClimb {
  index: number;
  grade: string;
  status: string;
  attempts: number;
  style?: string;
  topped?: boolean;
  notes?: string;
  logged_at: string;
}

interface ClimbLoggerProps {
  sessionId: string;
  surface: string;
  sessionMode: "template" | "free";
  presetName?: string;
  gymName?: string;
  targetGrade?: string;
  restSeconds?: number;
  tip?: string;
  targetClimbs?: string;
  onFinish: () => void;
  onClimbLogged?: (climb: LoggedClimb) => void;
}

const isLead = (surface: string) => surface === "gym_routes";

export function ClimbLogger({
  sessionId,
  surface,
  sessionMode,
  presetName,
  gymName,
  targetGrade,
  restSeconds,
  tip,
  targetClimbs,
  onFinish,
  onClimbLogged,
}: ClimbLoggerProps) {
  // Form state
  const [grade, setGrade] = useState(targetGrade || "6A");
  const [status, setStatus] = useState<"flash" | "sent" | "attempted">("flash");
  const [attempts, setAttempts] = useState(1);
  const [style, setStyle] = useState<string | undefined>(isLead(surface) ? "onsight" : undefined);
  const [topped, setTopped] = useState<boolean>(true);
  const [notes, setNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  // Session state
  const [climbs, setClimbs] = useState<Climb[]>([]);
  const [isLogging, setIsLogging] = useState(false);
  const [restKey, setRestKey] = useState(0);
  const [showRest, setShowRest] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const startedAt = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);

  // Elapsed timer
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 60000));
    }, 10000);
    return () => clearInterval(id);
  }, []);

  // Auto-set attempts based on status
  useEffect(() => {
    if (status === "flash") setAttempts(1);
    else if (status === "sent" && attempts < 2) setAttempts(2);
    else if (status === "attempted" && attempts < 1) setAttempts(1);
  }, [status, attempts]);

  // Lead style → auto attempts
  useEffect(() => {
    if (isLead(surface)) {
      if (style === "onsight" || style === "flash") {
        setStatus("flash");
        setAttempts(1);
      } else if (style === "redpoint") {
        setStatus("sent");
        if (attempts < 2) setAttempts(2);
      } else if (style === "project") {
        setStatus("attempted");
      }
    }
  }, [style, surface, attempts]);

  const handleLog = useCallback(async () => {
    if (isLogging) return;
    setIsLogging(true);
    try {
      const result = await logFreeClimb(sessionId, {
        grade,
        status,
        attempts,
        style: isLead(surface) ? style : undefined,
        topped: isLead(surface) ? topped : undefined,
        notes: notes || undefined,
      });

      const newClimb: Climb = {
        index: result.index,
        grade,
        status,
        attempts,
        style: isLead(surface) ? style : undefined,
        topped: isLead(surface) ? topped : undefined,
        notes: notes || undefined,
        logged_at: result.logged_at,
      };

      setClimbs((prev) => [newClimb, ...prev]);
      onClimbLogged?.(newClimb);

      // Reset form
      setStatus("flash");
      setNotes("");
      setShowNotes(false);
      if (isLead(surface)) {
        setStyle("onsight");
        setTopped(true);
      }

      // Start rest timer in template mode
      if (sessionMode === "template" && restSeconds) {
        setShowRest(true);
        setRestKey((k) => k + 1);
      }
    } catch (err) {
      console.error("Failed to log climb:", err);
    } finally {
      setIsLogging(false);
    }
  }, [sessionId, grade, status, attempts, style, topped, notes, surface, sessionMode, restSeconds, isLogging]);

  const targetMax = targetClimbs ? parseInt(targetClimbs.split("-")[1] || "0") : 0;
  const statusIcons = { flash: <Zap className="size-4" />, sent: <Check className="size-4" />, attempted: <X className="size-4" /> };
  const statusColors = {
    flash: "bg-amber-500/20 text-amber-400 border-amber-500/40",
    sent: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
    attempted: "bg-red-500/20 text-red-400 border-red-500/40",
  };

  return (
    <div className="flex flex-col gap-4 px-4 pb-32">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-lg font-semibold">
          {presetName && <>{presetName} &middot; </>}
          {surface === "gym_boulder" ? "Gym Boulder" :
           surface === "board_kilter" ? "Kilter" :
           surface === "board_moonboard" ? "Moon" :
           surface === "board_other" ? "Board" :
           "Lead"}
          {gymName && <> &middot; {gymName}</>}
        </h2>
        {sessionMode === "template" && targetGrade && restSeconds && (
          <p className="text-sm text-muted-foreground">
            Target: ~{targetGrade} &middot; Rest: {Math.floor(restSeconds / 60)}:{String(restSeconds % 60).padStart(2, "0")}
          </p>
        )}
      </div>

      {/* Phase tip */}
      {tip && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
          <p className="text-sm text-amber-200">{tip}</p>
        </div>
      )}

      {/* LOG FORM */}
      <div className="rounded-xl border bg-card p-4">
        <div className="mb-4">
          <GradePicker value={grade} onChange={setGrade} />
        </div>

        {/* Boulder status selector */}
        {!isLead(surface) && (
          <div className="mb-4 flex gap-2">
            {(["flash", "sent", "attempted"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2.5 text-sm font-medium transition-all ${
                  status === s ? statusColors[s] : "border-border text-muted-foreground hover:border-foreground/20"
                }`}
              >
                {statusIcons[s]}
                {s === "flash" ? "Flash" : s === "sent" ? "Sent" : "Tried"}
              </button>
            ))}
          </div>
        )}

        {/* Lead style selector */}
        {isLead(surface) && (
          <div className="mb-4 flex gap-2">
            {(["onsight", "flash", "redpoint", "project"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStyle(s)}
                className={`flex-1 rounded-lg border px-2 py-2.5 text-xs font-medium transition-all ${
                  style === s
                    ? "border-primary/50 bg-primary/20 text-primary"
                    : "border-border text-muted-foreground hover:border-foreground/20"
                }`}
              >
                {s === "onsight" ? "OS" : s === "flash" ? "FL" : s === "redpoint" ? "RP" : "PROJ"}
              </button>
            ))}
          </div>
        )}

        {/* Lead topped toggle */}
        {isLead(surface) && (
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => setTopped(true)}
              className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-all ${
                topped
                  ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-400"
                  : "border-border text-muted-foreground"
              }`}
            >
              Topped
            </button>
            <button
              onClick={() => setTopped(false)}
              className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-all ${
                !topped
                  ? "border-red-500/50 bg-red-500/20 text-red-400"
                  : "border-border text-muted-foreground"
              }`}
            >
              Fell
            </button>
          </div>
        )}

        {/* Attempts picker (visible for sent/attempted boulder, redpoint/project lead) */}
        {(((!isLead(surface) && status !== "flash") ||
          (isLead(surface) && (style === "redpoint" || style === "project"))) && (
          <div className="mb-4 flex items-center justify-center gap-4">
            <span className="text-sm text-muted-foreground">Attempts:</span>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => setAttempts(Math.max(status === "sent" ? 2 : 1, attempts - 1))}
            >
              <Minus className="size-4" />
            </Button>
            <span className="min-w-[32px] text-center text-xl font-bold tabular-nums">{attempts}</span>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => setAttempts(Math.min(20, attempts + 1))}
            >
              <Plus className="size-4" />
            </Button>
          </div>
        ))}

        {/* Notes toggle */}
        {!showNotes ? (
          <button
            onClick={() => setShowNotes(true)}
            className="mb-3 text-xs text-muted-foreground hover:text-foreground"
          >
            + Add note
          </button>
        ) : (
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add a note..."
            className="mb-3 w-full rounded-lg border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/50"
          />
        )}

        {/* LOG button */}
        <Button
          onClick={handleLog}
          disabled={isLogging}
          className="w-full text-base font-semibold"
          size="lg"
        >
          {isLogging ? "Logging..." : isLead(surface) ? "Log Route" : "Log Boulder"}
        </Button>
      </div>

      {/* Rest timer */}
      {sessionMode === "template" && restSeconds && showRest ? (
        <RestTimer
          key={restKey}
          initialSeconds={restSeconds}
          autoStart={true}
          onComplete={() => setShowRest(false)}
        />
      ) : sessionMode === "free" ? (
        <RestTimer initialSeconds={180} autoStart={false} />
      ) : null}

      {/* Climb history */}
      {climbs.length > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Logged</span>
            <span className="text-sm text-muted-foreground">
              {climbs.length}{targetMax > 0 ? `/${targetMax}` : ""} {isLead(surface) ? "routes" : "boulders"}
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            {climbs.map((c) => (
              <div key={c.index} className="flex items-center gap-2 text-sm">
                <span className="w-6 text-right text-xs text-muted-foreground">#{c.index}</span>
                <span className="font-medium">{c.grade}</span>
                <span className={`flex items-center gap-0.5 ${
                  c.status === "flash" ? "text-amber-400" :
                  c.status === "sent" ? "text-emerald-400" : "text-red-400"
                }`}>
                  {statusIcons[c.status as keyof typeof statusIcons]}
                  {c.status}
                  {c.status !== "flash" && <span className="text-muted-foreground">({c.attempts})</span>}
                </span>
                {isLead(surface) && c.style && (
                  <span className="text-xs text-muted-foreground uppercase">{c.style}</span>
                )}
                {c.notes && <span className="truncate text-xs text-muted-foreground">{c.notes}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {isLead(surface) ? "Routes" : "Boulders"}: {climbs.length}
          {targetMax > 0 && `/${targetMax}`}
        </span>
        <span>{elapsed} min</span>
      </div>

      {/* Finish button */}
      {!showConfirm ? (
        <Button
          variant="outline"
          onClick={() => setShowConfirm(true)}
          className="w-full"
        >
          Finish Session
        </Button>
      ) : (
        <div className="rounded-xl border bg-card p-4">
          <p className="mb-3 text-center text-sm">
            Finish session? You logged {climbs.length} {isLead(surface) ? "routes" : "boulders"}.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowConfirm(false)} className="flex-1">
              Cancel
            </Button>
            <Button onClick={onFinish} className="flex-1">
              Finish
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
