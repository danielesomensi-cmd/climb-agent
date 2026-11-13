"use client";

import { useState } from "react";
import { toast } from "sonner";
import type {
  OutdoorSpot,
  OutdoorRoute,
  OutdoorSession,
  OutdoorDayType,
  OutdoorRouteProfile,
  OutdoorConditions,
} from "@/lib/types";
import { ApiError, getOutdoorLogByDate, postOutdoorLog, putOutdoorLog } from "@/lib/api";
import { useSubmitLock } from "@/lib/hooks/use-submit-lock";
import { enqueue } from "@/lib/outbox";
import { deriveTryTimings, routeHasTimestamps } from "@/lib/try-timings";
import {
  TECHNIQUE_METRICS,
  TECHNIQUE_SAMPLE_MAX,
  TECHNIQUE_VALUE_MAX,
  parseTechniqueDraft,
  techniqueDraftOf,
  techniqueTargetField,
  type TechniqueDraft,
} from "@/lib/outdoor-technique";
import { TryBreakdown } from "@/components/outdoor/try-breakdown";
import {
  attemptChipClass,
  attemptLabel,
  attemptResultLabel,
  isBoulderRoute,
  nextAttemptResult,
  nextRopeRole,
  ropeRoleName,
  ropeRoleOf,
  ropeRoleShort,
  routeLeadSent,
  stripRopeOnly,
  withRopeRole,
} from "@/lib/outdoor-result";
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

const FRENCH_SPORT_GRADES = [
  "4a","4b","4c","5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

const FONT_BOULDER_GRADES = [
  "4","4+","5","5+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
];

/** mm:ss for a duration in seconds (B264 — rest/climb summary display). */
/** B279 — timing totals for a route: sum of per-attempt values when present,
 *  else the A227 route-level value (first burn only on legacy logs). */
function routeTiming(route: OutdoorRoute): { climb: number | null; rest: number | null } {
  const climbs = route.attempts.filter((a) => typeof a.climb_seconds === "number");
  const rests = route.attempts.filter((a) => typeof a.rest_seconds === "number");
  return {
    climb: climbs.length
      ? climbs.reduce((s, a) => s + (a.climb_seconds ?? 0), 0)
      : typeof route.climb_seconds === "number" ? route.climb_seconds : null,
    rest: rests.length
      ? rests.reduce((s, a) => s + (a.rest_seconds ?? 0), 0)
      : typeof route.rest_seconds === "number" ? route.rest_seconds : null,
  };
}

function fmtSec(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** A324: a style says how a send went — a route that loses its last send on
 *  lead (a tap on the result or on the role) loses its style too. */
function keepStyleOnlyWithLeadSend(before: OutdoorRoute, after: OutdoorRoute): OutdoorRoute {
  if (!after.style || !routeLeadSent(before) || routeLeadSent(after)) return after;
  const next = { ...after };
  delete next.style;
  return next;
}

const sameCrag = (a: string, b: string) =>
  a.trim().replace(/\s+/g, " ").toLowerCase() === b.trim().replace(/\s+/g, " ").toLowerCase();

/**
 * A324 (B401 residual, point 4) — before «Add as another crag»: is that crag
 * already logged on `date`? Since B412 a POST on a (date, crag) that exists is
 * added to that crag's log (it used to replace it): a new log typed under a
 * logged crag is most likely the same outing logged twice, so «add» and the
 * new-log form refuse it. `null` = could not check.
 */
async function cragLoggedOn(date: string, spotName: string): Promise<boolean | null> {
  try {
    const res = await getOutdoorLogByDate(date);
    const rows = res.sessions ?? (res.session ? [res.session] : []);
    return rows.some((r) => sameCrag(r.spot_name ?? "", spotName));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return false;
    return null;
  }
}

/** Save paths: the plain button, or the two answers of the rename dialog. */
type SaveMode = "save" | "rename" | "add";

interface Props {
  spots: OutdoorSpot[];
  defaultDate?: string;
  defaultSpotName?: string;
  defaultDiscipline?: "lead" | "boulder" | "both";
  defaultGrade?: string;
  defaultDuration?: number;
  initialData?: OutdoorSession;
  /** B371: `planSynced` — the server already marked the plan day done (B273);
   * the caller must not resend complete_outdoor on its pre-log copy. */
  onSuccess?: (info?: { planSynced?: boolean }) => void;
  // A226 — guided finish flow: carry day_type/route_profile/conditions and
  // submit through a custom handler (finishOutdoorSession) instead of post/put.
  dayType?: OutdoorDayType;
  routeProfile?: OutdoorRouteProfile;
  conditions?: OutdoorConditions | null;
  durationCappedNote?: { cap: number; raw: number } | null;
  onSubmit?: (payload: Record<string, unknown>) => Promise<void>;
  submitLabel?: string;
  // A226 — routes captured live during the active session (prefill, not edit mode).
  initialRoutes?: OutdoorRoute[];
  /** B412: the form finishes a live session (one started offline posts a new
   *  log here). At a crag already logged that day it joins that crag's log on
   *  the server, so the B410 «already logged» refusal does not apply. */
  liveSession?: boolean;
}

export default function OutdoorLogForm({ spots, defaultDate, defaultSpotName, defaultDiscipline, defaultGrade, defaultDuration, initialData, onSuccess, dayType, routeProfile, conditions, durationCappedNote, onSubmit, submitLabel, initialRoutes, liveSession = false }: Props) {
  const isEdit = !!initialData;
  const [date, setDate] = useState(initialData?.date || defaultDate || new Date().toISOString().slice(0, 10));
  const [spotName, setSpotName] = useState(initialData?.spot_name || defaultSpotName || "");
  const [discipline, setDiscipline] = useState<"lead" | "boulder" | "both">(initialData?.discipline || defaultDiscipline || "boulder");
  const [duration, setDuration] = useState(initialData?.duration_minutes || defaultDuration || 120);
  const [routes, setRoutes] = useState<OutdoorRoute[]>(initialData?.routes || initialRoutes || []);
  const [notes, setNotes] = useState(initialData?.notes || "");
  const [error, setError] = useState<string | null>(null);
  // A324 (B-OUTDOOR-CRAG-PICKER point 4): an edit whose crag name changed asks
  // «rename it, or add another crag?» instead of guessing.
  const [askCrag, setAskCrag] = useState(false);
  const originalSpot = initialData?.spot_name ?? "";
  const cragChanged = isEdit && !sameCrag(spotName, originalSpot);
  // A324 review: the first `editedCragRoutes` routes of the list are the
  // edited crag's own (routes are only appended, never reordered). «Add as
  // another crag» saves only the ones after them — never the edited crag's.
  const [editedCragRoutes, setEditedCragRoutes] = useState(initialData?.routes?.length ?? 0);
  // A330 (D288-FE) — the crag day's technique target (A329): the day ticks the
  // week's technique key only with one. Prefilled from the log on an edit.
  const initialTechnique = initialData?.technique_target ?? null;
  const [technique, setTechnique] = useState<TechniqueDraft>(() => techniqueDraftOf(initialTechnique));
  const parsedTechnique = parseTechniqueDraft(technique);
  const techniqueHint = TECHNIQUE_METRICS.find((m) => m.value === technique.metric)?.hint;

  const gradeList = discipline === "lead" || discipline === "both"
    ? FRENCH_SPORT_GRADES
    : FONT_BOULDER_GRADES;
  const initialGrade = defaultGrade && gradeList.includes(defaultGrade) ? defaultGrade : "6a";

  // Issue 1: append at bottom
  const addRoute = () => {
    setRoutes([...routes, { name: "", grade: initialGrade, attempts: [{ result: "sent" }] }]);
  };

  const updateRoute = (idx: number, field: keyof OutdoorRoute, value: string) => {
    const updated = [...routes];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    setRoutes(updated);
  };

  /** A324: a route on a rope can carry a rope role and A0; a boulder cannot. */
  const onRope = (route: OutdoorRoute) => !isBoulderRoute(route, discipline);

  /** Apply `change` to one attempt, then drop the style if the route lost its
   *  last send on lead (it used to drop it on any un-send). */
  const changeAttempt = (rIdx: number, aIdx: number, change: (r: OutdoorRoute, a: OutdoorRoute["attempts"][number]) => OutdoorRoute["attempts"][number]) =>
    setRoutes((cur) =>
      cur.map((r, i) => {
        if (i !== rIdx) return r;
        const attempts = r.attempts.map((a, j) => (j === aIdx ? change(r, a) : a));
        return keepStyleOnlyWithLeadSend(r, { ...r, attempts });
      }),
    );

  /**
   * F39 (A245) — era un ciclo sent → fell → RIMOZIONE: un doppio tap
   * accidentale sul badge cancellava il tentativo. Ora è un giro puro senza
   * rimozione; la rimozione ha il suo ✕ dedicato con undo.
   * A324: on a rope sent → fell → A0 → sent, on a boulder sent ⇄ fell.
   * B393: a top with rests is never promoted to a send by a tap (→ fell).
   */
  const toggleAttempt = (rIdx: number, aIdx: number) =>
    changeAttempt(rIdx, aIdx, (r, a) => ({ ...a, result: nextAttemptResult(a.result, onRope(r)) }));

  /** A324: who led this try — Lead → 2nd → TR → Lead (lead written as absent). */
  const toggleRole = (rIdx: number, aIdx: number) =>
    changeAttempt(rIdx, aIdx, (_r, a) => withRopeRole(a, nextRopeRole(ropeRoleOf(a))));

  /** A324: a boulder has no rope. Switching the session to boulder drops the
   *  rope roles and turns A0 into a fall, as the server would on save. */
  const changeDiscipline = (d: "lead" | "boulder" | "both") => {
    setDiscipline(d);
    if (d !== "boulder") return;
    let changed = false;
    const next = routes.map((r) => {
      if (!isBoulderRoute(r, d)) return r;
      const stripped = stripRopeOnly(r);
      if (stripped !== r) changed = true;
      return stripped;
    });
    if (changed) {
      setRoutes(next);
      toast("Boulder: no rope roles, and A0 became Fell.", { duration: 6000 });
    }
  };

  /** F39 — rimozione esplicita di un tentativo, con undo di 10s. */
  const removeAttempt = (rIdx: number, aIdx: number) => {
    const removed = routes[rIdx].attempts[aIdx];
    setRoutes((cur) =>
      cur.map((r, i) =>
        i === rIdx ? { ...r, attempts: r.attempts.filter((_, j) => j !== aIdx) } : r,
      ),
    );
    toast("Attempt removed", {
      duration: 10_000,
      action: {
        label: "Undo",
        onClick: () =>
          setRoutes((cur) =>
            cur.map((r, i) => {
              if (i !== rIdx) return r;
              const attempts = [...r.attempts];
              attempts.splice(Math.min(aIdx, attempts.length), 0, removed);
              return { ...r, attempts };
            }),
          ),
      },
    });
  };

  /** A new try on the route, with the rope role of its last try (A324). */
  const addAttempt = (rIdx: number) =>
    setRoutes((cur) =>
      cur.map((r, i) => {
        if (i !== rIdx) return r;
        const last = r.attempts[r.attempts.length - 1];
        const role = onRope(r) ? ropeRoleOf(last) : "lead";
        return { ...r, attempts: [...r.attempts, withRopeRole({ result: "sent" as const }, role)] };
      }),
    );

  const updateStyle = (rIdx: number, value: string) => {
    const updated = [...routes];
    if (value) {
      (updated[rIdx] as unknown as Record<string, unknown>).style = value;
    } else {
      delete (updated[rIdx] as unknown as Record<string, unknown>).style;
    }
    setRoutes(updated);
  };

  const removeRoute = (idx: number) => {
    setRoutes(routes.filter((_, i) => i !== idx));
    if (idx < editedCragRoutes) setEditedCragRoutes((n) => n - 1);
  };

  /** Routes as saved: complete ones only, `style` only when set. */
  const savedRoutes = (list: OutdoorRoute[]) =>
    list.filter(r => r.name && r.grade).map(r => {
      const { style, ...rest } = r;
      return style ? { ...rest, style } : rest;
    });

  /** The log body. `forEdit`: emptied notes go as `null`, an explicit clear
   *  (an edit keeps the keys it does not send, routes and notes excepted). */
  const buildPayload = (forEdit: boolean): Record<string, unknown> => {
    const payload: Record<string, unknown> = {
      date,
      spot_name: spotName.trim(),
      discipline,
      duration_minutes: duration,
      routes: savedRoutes(routes),
      notes: notes || (forEdit ? null : undefined),
    };
    // A226 — carry outdoor.v2 fields when provided (guided flow).
    if (dayType) payload.day_type = dayType;
    if (routeProfile && Object.keys(routeProfile).length > 0) payload.route_profile = routeProfile;
    if (conditions) payload.conditions = conditions;
    // A330 — `technique_target` as the schema wants it; on an edit, left out
    // keeps the stored one and null clears it (A324).
    const tt = techniqueTargetField(parsedTechnique.target, forEdit ? "put" : "post", initialTechnique);
    if (tt !== undefined) payload.technique_target = tt;
    return payload;
  };

  /**
   * A324 review — «Add <new> as another crag»: the form still holds the edited
   * crag's routes, notes and duration. The new crag gets only what was added
   * here: the routes after the edited crag's, the notes and the duration only
   * if changed (else no notes and the new-log default). Saving the edited
   * crag's routes again would count them twice — load, stats, A292 evidence.
   */
  const addedRoutes = savedRoutes(routes.slice(editedCragRoutes));
  const notesChanged = notes !== (initialData?.notes || "");
  const addDuration = duration !== initialData?.duration_minutes ? duration : defaultDuration || 120;
  const buildAddPayload = (): Record<string, unknown> => {
    const payload = buildPayload(false);
    payload.routes = addedRoutes;
    payload.duration_minutes = addDuration;
    if (!notesChanged) delete payload.notes;
    // A330: the edited crag's technique target stays with it — only one typed here goes.
    const tt = techniqueTargetField(parsedTechnique.target, "add", initialTechnique);
    if (tt === undefined) delete payload.technique_target;
    else payload.technique_target = tt;
    return payload;
  };

  /** A new crag log. A245 B-4 (F5) — append-only and self-contained, so it
   *  can safely wait in the outbox. An EDIT (putOutdoorLog) cannot: replaying
   *  it hours later would clobber whatever changed in between. */
  const postNewLog = async (payload: Record<string, unknown>): Promise<boolean | undefined> => {
    try {
      return (await postOutdoorLog(payload as unknown as Omit<OutdoorSession, "log_version">))?.plan_synced;
    } catch (err) {
      const queued = enqueue("outdoor_log", payload);
      if (!queued) throw err;
      toast("Session saved on this device — it will sync when you're back online.", {
        duration: 6000,
      });
      return undefined;
    }
  };

  // B330: the lock is a ref, so a double tap cannot slip a second POST through
  // the window between `setBusy(true)` and the re-render that disables the
  // button. Logging the same day twice is otherwise a real path — the plan-sync
  // side effect runs again and the day's ripple is recomputed.
  const { run: submit, busy: submitting } = useSubmitLock(async (mode: SaveMode) => {
    if (!spotName.trim()) {
      setError("Spot name is required");
      return;
    }
    // A330: a technique number the server would refuse (422) never leaves the form.
    if (parsedTechnique.error) {
      setError(parsedTechnique.error);
      return;
    }
    // A324 (B-OUTDOOR-CRAG-PICKER point 4): «Log outdoor» / «Quick log» open
    // the day's crag in edit mode, so a new name typed here is either a rename
    // or the day's second crag. Ask — never guess.
    if (mode === "save" && cragChanged && !onSubmit) {
      setAskCrag(true);
      return;
    }
    setError(null);
    try {
      let planSynced: boolean | undefined;
      if (onSubmit) {
        await onSubmit(buildPayload(false));
      } else if (isEdit && mode !== "add") {
        // B401 (point 2): name the crag being edited, so a rename is a rename.
        planSynced = (await putOutdoorLog({
          ...(buildPayload(true) as unknown as Omit<OutdoorSession, "log_version">),
          original_spot_name: originalSpot,
        }))?.plan_synced;
      } else {
        if (mode === "add") {
          // The crag being edited stays as it is: this is a NEW crag of the day.
          const taken = await cragLoggedOn(date, spotName);
          if (taken !== false) {
            setError(
              taken
                ? `${spotName.trim()} is already logged on ${date} — nothing saved. Open that crag to edit it.`
                : "Couldn't check the crags logged on that date — nothing saved. Please try again.",
            );
            return;
          }
        }
        if (mode !== "add" && !liveSession) {
          // B410: a new log under a crag already logged that day — «Add
          // another crag» typed with the logged crag's name, or a date changed
          // in the new-log form — is most likely the same outing logged twice.
          // Since B412 the server adds it to that crag's log (it used to
          // replace it), so it would count twice: refused here. A live session
          // is the exception: it is a new session by definition, and the
          // server folds it into the crag's log (B412). When the check cannot
          // run (offline), the log goes as before: the outbox keeps offline
          // logging possible.
          if ((await cragLoggedOn(date, spotName)) === true) {
            setError(`${spotName.trim()} is already logged on ${date} — nothing saved. Open that crag to edit it.`);
            return;
          }
        }
        planSynced = await postNewLog(mode === "add" ? buildAddPayload() : buildPayload(false));
      }
      onSuccess?.({ planSynced });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to log session");
    }
  });

  // A241 — derived per-try rest/climb (session-wide chronological rule).
  const tryTimings = deriveTryTimings(routes);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">{isEdit ? "Edit Outdoor Session" : "Log Outdoor Session"}</h3>

      {/* Date */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Date</label>
        {/* B410: an edit stays on its day. Moving it replaced a same-name crag
            on the new date and left the old entry behind (B401 review). */}
        <input
          type="date"
          value={date}
          onChange={e => setDate(e.target.value)}
          disabled={isEdit}
          aria-describedby={isEdit ? "outdoor-date-locked" : undefined}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-70"
        />
        {isEdit && (
          <p id="outdoor-date-locked" className="mt-1 text-xs text-muted-foreground">
            The date can&apos;t change here. To move this session, delete it and log it again on the right day.
          </p>
        )}
      </div>

      {/* Spot */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Spot</label>
        {spots.length > 0 ? (
          <select
            value={spotName}
            onChange={e => setSpotName(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select or type below...</option>
            {spots.map(s => (
              <option key={s.id} value={s.name}>{s.name}</option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          placeholder="Spot name"
          value={spotName}
          onChange={e => setSpotName(e.target.value)}
          className="w-full mt-1 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {/* Discipline */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Discipline</label>
        <div className="flex gap-2">
          {(["boulder", "lead", "both"] as const).map(d => (
            <button
              key={d}
              onClick={() => changeDiscipline(d)}
              className={`rounded-md px-3 py-1.5 text-sm border ${
                discipline === d ? "bg-primary text-primary-foreground" : "bg-background"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Duration */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Duration (min)</label>
        <input
          type="number"
          inputMode="numeric"
          value={duration}
          onChange={e => setDuration(Number(e.target.value))}
          min={1}
          className="w-24 rounded-md border bg-background px-3 py-2 text-sm"
        />
        {durationCappedNote && (
          <p className="mt-1 text-xs text-amber-500">
            Timer ran long ({Math.round(durationCappedNote.raw / 60)}h) — capped to {durationCappedNote.cap} min. Adjust above if needed.
          </p>
        )}
      </div>

      {/* Routes — Issue 2: 2-row layout per card */}
      <div>
        <label className="text-sm font-medium">Routes / Problems</label>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Log your routes and tries. Tap + to add a try, ✕ to remove one. Tap a result to change it: Sent → Fell → A0 on a rope, Sent ⇄ Fell on a boulder. Tap L / 2nd / TR to say who led: only a send on lead counts as a send — clean on second or top-rope shows in blue. Climb Agent tracks your history and adapts your training based on what you climb outdoors.
        </p>

        <div className="mt-2 space-y-2">
          {routes.map((route, rIdx) => (
            <div key={rIdx} className="rounded-lg border p-3 space-y-2">
              {/* Row 1: Name + Grade + Delete */}
              <div className="flex gap-2">
                <input
                  placeholder="Name"
                  value={route.name}
                  onChange={e => updateRoute(rIdx, "name", e.target.value)}
                  className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-sm"
                />
                <select
                  value={route.grade}
                  onChange={e => updateRoute(rIdx, "grade", e.target.value)}
                  className="w-[72px] shrink-0 rounded-md border bg-background px-2 py-1.5 text-sm"
                >
                  {gradeList.map(g => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
                <button
                  onClick={() => removeRoute(rIdx)}
                  className="shrink-0 rounded-md border px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                  aria-label="Remove route"
                >
                  ✕
                </button>
              </div>

              {/* Row 2: Style + attempt badges + add attempt */}
              <div className="flex flex-wrap items-center gap-1.5">
                <select
                  value={route.style || ""}
                  onChange={e => updateStyle(rIdx, e.target.value)}
                  className="rounded-md border bg-background px-2 py-1 text-xs"
                >
                  <option value="">Style</option>
                  <option value="onsight">🟢 OS</option>
                  <option value="flash">🟡 FL</option>
                  <option value="redpoint">🔴 RP</option>
                  <option value="project">⚪ PRJ</option>
                </select>

                {/* F39: il badge fa solo il giro dell'esito; il ✕ rimuove (con undo).
                    A324: [ruolo L/2nd/TR] [esito] [✕] — il ruolo solo in corda. */}
                {route.attempts.map((a, aIdx) => {
                  const rope = onRope(route);
                  const role = ropeRoleOf(a);
                  const cycleHint = rope ? "Tap to cycle Sent → Fell → A0" : "Tap to switch Sent ⇄ Fell";
                  const tryName = `${route.name.trim() || `Route ${rIdx + 1}`} try ${aIdx + 1}`;
                  return (
                    <span key={aIdx} className="inline-flex overflow-hidden rounded border border-border">
                      {rope && (
                        <button
                          type="button"
                          onClick={() => toggleRole(rIdx, aIdx)}
                          aria-label={`${tryName}, who led: ${ropeRoleName(role)} — tap to change`}
                          title="Who led: Lead → 2nd → TR"
                          className={`min-h-[44px] min-w-[40px] border-r border-border px-2 text-xs font-medium ${
                            role === "lead" ? "bg-muted text-muted-foreground" : "bg-info/15 text-info"
                          }`}
                        >
                          {ropeRoleShort(role)}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => toggleAttempt(rIdx, aIdx)}
                        aria-label={`${tryName}, result: ${attemptLabel(a)} — ${cycleHint.toLowerCase()}`}
                        className={`min-h-[44px] px-3 text-sm font-medium ${attemptChipClass(a)}`}
                        title={cycleHint}
                      >
                        {attemptResultLabel(a)}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeAttempt(rIdx, aIdx)}
                        aria-label={`Remove attempt ${aIdx + 1}`}
                        className="min-h-[44px] border-l border-border bg-muted px-2.5 text-sm text-muted-foreground hover:text-foreground"
                      >
                        ✕
                      </button>
                    </span>
                  );
                })}

                <button
                  onClick={() => addAttempt(rIdx)}
                  aria-label="Add attempt"
                  className="min-h-[44px] rounded border px-3 text-sm text-muted-foreground hover:text-foreground"
                >
                  +
                </button>
              </div>

              {/* A241 — per-try rest/climb breakdown when timestamps exist;
                  B264 / B265 / B279 totals as the legacy fallback */}
              {routeHasTimestamps(route) ? (
                <TryBreakdown attempts={route.attempts} timings={tryTimings[rIdx]} />
              ) : (() => {
                const t = routeTiming(route);
                const multi = route.attempts.length > 1;
                if (t.climb == null && t.rest == null) return null;
                return (
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    {t.climb != null && (
                      <span title={multi ? `Total time on the wall (${route.attempts.length} tries)` : "Time on the wall"} className="text-amber-500/80">climb {fmtSec(t.climb)}</span>
                    )}
                    {t.climb != null && t.rest != null && (
                      <span aria-hidden="true">·</span>
                    )}
                    {t.rest != null && (
                      <span title={multi ? `Total rest (${route.attempts.length} tries)` : "Rest taken before this burn"}>rest {fmtSec(t.rest)}</span>
                    )}
                  </div>
                );
              })()}
            </div>
          ))}
        </div>

        {/* Issue 3: "+ Add route" below last card, left-aligned */}
        <button
          onClick={addRoute}
          className="mt-2 text-sm text-primary hover:underline"
        >
          + Add route
        </button>
      </div>

      {/* A330 (D288-FE) — technique target (A329): optional, one per crag. */}
      <div className="rounded-lg border p-3 space-y-2" data-testid="technique-target">
        <div>
          <label htmlFor="technique-metric" className="text-sm font-medium">
            Technique (counts for the key)
          </label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Optional. Log one number and this day ticks the week&apos;s technique key — what counts is
            that you measured it, not how good it is.
          </p>
        </div>
        <select
          id="technique-metric"
          value={technique.metric}
          onChange={(e) => setTechnique((t) => ({ ...t, metric: e.target.value as TechniqueDraft["metric"] }))}
          className="w-full min-h-[44px] rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">Not measured</option>
          {TECHNIQUE_METRICS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        {technique.metric && (
          <>
            {techniqueHint && <p className="text-xs text-muted-foreground">{techniqueHint}</p>}
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="decimal"
                aria-label={`Technique number (0-${TECHNIQUE_VALUE_MAX})`}
                placeholder={`0-${TECHNIQUE_VALUE_MAX}`}
                value={technique.value}
                onChange={(e) => setTechnique((t) => ({ ...t, value: e.target.value }))}
                className="w-24 min-h-[44px] shrink-0 rounded-md border bg-background px-3 py-2 text-sm"
              />
              <input
                type="text"
                aria-label="Route or pitch measured (optional)"
                placeholder="Route / pitch (optional)"
                maxLength={TECHNIQUE_SAMPLE_MAX}
                value={technique.sample}
                onChange={(e) => setTechnique((t) => ({ ...t, sample: e.target.value }))}
                className="min-w-0 flex-1 min-h-[44px] rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>
          </>
        )}
      </div>

      {/* Notes */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Notes</label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        onClick={() => void submit("save")}
        disabled={submitting}
        className="w-full min-h-[44px] rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {submitting ? "Saving..." : submitLabel || (isEdit ? "Save Changes" : "Log Session")}
      </button>

      {/* A324 (B-OUTDOOR-CRAG-PICKER point 4) — the crag name changed in edit
          mode: rename this crag, or add the new one as another crag of the day. */}
      <AlertDialog open={askCrag} onOpenChange={setAskCrag}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rename the crag or add another?</AlertDialogTitle>
            <AlertDialogDescription>
              This session is logged at <span className="text-foreground">{originalSpot}</span>. Rename it to{" "}
              <span className="text-foreground">{spotName.trim()}</span>, routes and all, or keep {originalSpot} as
              it is and add <span className="text-foreground">{spotName.trim()}</span> as another crag of the day
              with only what you added in this form:{" "}
              <span className="text-foreground">
                {addedRoutes.length === 0
                  ? "no routes"
                  : `${addedRoutes.length} ${addedRoutes.length === 1 ? "route" : "routes"}`}
                , {addDuration} min{notesChanged && notes ? ", your notes" : ""}
              </span>
              . {originalSpot}&apos;s routes, notes and duration stay with {originalSpot}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-auto min-h-[44px]">Keep editing</AlertDialogCancel>
            <AlertDialogAction
              variant="outline"
              className="h-auto min-h-[44px] whitespace-normal"
              onClick={() => void submit("add")}
            >
              Add {spotName.trim()} as another crag
            </AlertDialogAction>
            <AlertDialogAction
              className="h-auto min-h-[44px] whitespace-normal"
              onClick={() => void submit("rename")}
            >
              Rename {originalSpot} to {spotName.trim()}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
