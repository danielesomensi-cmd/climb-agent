"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { useUserState } from "@/lib/hooks/use-state";
import { computeAssessment, generateMacrocycle, deleteState, putState, getWeek, getOutdoorSpots, addOutdoorSpot, deleteOutdoorSpot, exportUserState, importUserState, generateRecoveryCode } from "@/lib/api";
import type { OutdoorSpot } from "@/lib/types";
import { AvailabilityEditor } from "@/components/settings/availability-editor";
import { EquipmentEditor } from "@/components/settings/equipment-editor";
import { GoalEditor } from "@/components/settings/goal-editor";
import { LimitationsEditor, LimitationsSummary } from "@/components/settings/limitations-editor";
import { ProfileAssessmentEditor } from "@/components/settings/profile-assessment-editor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { isVoiceCuesEnabled, setVoiceCuesEnabled } from "@/lib/voice-cues";

export default function SettingsPage() {
  const { state, loading, error, refresh } = useUserState();
  const router = useRouter();

  const [regeneratingMacro, setRegeneratingMacro] = useState(false);
  const [restartMacroDialogOpen, setRestartMacroDialogOpen] = useState(false);
  const [restartMacroConfirmOpen, setRestartMacroConfirmOpen] = useState(false);
  const [restartingMacro, setRestartingMacro] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingAvailability, setEditingAvailability] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState(false);
  const [editingLimitations, setEditingLimitations] = useState(false);
  const [equipmentSavedOpen, setEquipmentSavedOpen] = useState(false);
  const [goalEditorOpen, setGoalEditorOpen] = useState(false);
  const [savingGoal, setSavingGoal] = useState(false);
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [outdoorSpots, setOutdoorSpots] = useState<OutdoorSpot[]>([]);
  const [addingSpot, setAddingSpot] = useState(false);
  const [newSpotName, setNewSpotName] = useState("");
  const [newSpotDiscipline, setNewSpotDiscipline] = useState<"lead" | "boulder" | "both">("boulder");
  const [voiceCuesOn, setVoiceCuesOn] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);
  const [recoverInputOpen, setRecoverInputOpen] = useState(false);
  const [recoverInput, setRecoverInput] = useState("");
  const [recovering, setRecovering] = useState(false);
  const [recoverError, setRecoverError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [backupMsg, setBackupMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => { setVoiceCuesOn(isVoiceCuesEnabled()); }, []);
  useEffect(() => { setUserId(localStorage.getItem("climb_user_id")); }, []);

  async function handleGenerateCode() {
    setGeneratingCode(true);
    try {
      const { recovery_code } = await generateRecoveryCode();
      setRecoveryCode(recovery_code);
    } catch {
      /* ignore */
    } finally {
      setGeneratingCode(false);
    }
  }

  // Load existing recovery code on mount (silently)
  useEffect(() => {
    generateRecoveryCode().then(({ recovery_code }) => setRecoveryCode(recovery_code)).catch(() => {});
  }, []);

  async function handleRecoverSubmit() {
    const trimmed = recoverInput.trim().toUpperCase();
    if (!trimmed) return;
    setRecovering(true);
    setRecoverError(null);
    try {
      const { recoverAccount } = await import("@/lib/api");
      const { uuid } = await recoverAccount(trimmed);
      localStorage.setItem("climb_user_id", uuid);
      window.location.href = "/today";
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setRecoverError("Code not found. Check and try again.");
      } else {
        setRecoverError("Something went wrong. Please try again.");
      }
    } finally {
      setRecovering(false);
    }
  }

  const loadSpots = useCallback(async () => {
    try {
      const data = await getOutdoorSpots();
      setOutdoorSpots(data.spots);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSpots(); }, [loadSpots]);

  async function handleAddSpot() {
    if (!newSpotName.trim()) return;
    try {
      await addOutdoorSpot({ name: newSpotName.trim(), discipline: newSpotDiscipline });
      setNewSpotName("");
      setAddingSpot(false);
      await loadSpots();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to add spot");
    }
  }

  async function handleDeleteSpot(spotId: string) {
    try {
      await deleteOutdoorSpot(spotId);
      await loadSpots();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to delete spot");
    }
  }

  // User data
  const user = state?.user ?? {};
  const assessment = state?.assessment ?? {};
  const body = (state as Record<string, unknown>)?.body as Record<string, number> | undefined;
  const goal = state?.goal ?? {};
  const equipment = (state?.equipment ?? {}) as {
    home_enabled?: boolean;
    home?: string[];
    gyms?: Array<{ gym_id: string; name: string; equipment: string[] }>;
  };
  const availability = (state?.availability ?? {}) as Record<
    string,
    Record<string, { available: boolean; preferred_location?: string; gym_id?: string }>
  >;

  /** Save updated availability and regenerate plan */
  async function handleSaveAvailability(
    newAvailability: Record<string, unknown>,
    newPrefs: { target_training_days_per_week: number; hard_day_cap_per_week: number },
  ) {
    setActionError(null);
    try {
      await putState({ availability: newAvailability, planning_prefs: newPrefs });
      await getWeek(0, true);
      await refresh();
      setEditingAvailability(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to save availability");
    }
  }

  /** Save updated limitations */
  async function handleSaveLimitations(newLimitations: { active_flags?: string[]; details?: Array<{ area: string; side: string; severity: string; notes?: string }> }) {
    setActionError(null);
    try {
      await putState({ limitations: newLimitations });
      await refresh();
      setEditingLimitations(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to save limitations");
    }
  }

  /** Save updated equipment */
  async function handleSaveEquipment(newEquipment: Record<string, unknown>) {
    setActionError(null);
    try {
      await putState({ equipment: newEquipment });
      await refresh();
      setEditingEquipment(false);
      setEquipmentSavedOpen(true);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to save equipment");
    }
  }

  /** Save updated goal and regenerate plan */
  async function handleGoalConfirm(newGoal: Record<string, unknown>) {
    setSavingGoal(true);
    setActionError(null);
    try {
      await putState({ goal: newGoal });
      await computeAssessment(state?.assessment, newGoal);
      await generateMacrocycle();
      await refresh();
      setGoalEditorOpen(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to update goal");
    } finally {
      setSavingGoal(false);
    }
  }

  /** Save updated profile/assessment and recompute assessment */
  async function handleProfileConfirm(patch: Record<string, unknown>) {
    setSavingProfile(true);
    setActionError(null);
    try {
      await putState({ assessment: patch });
      await computeAssessment({ ...state?.assessment, ...patch }, state?.goal);
      await refresh();
      setProfileEditorOpen(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to update profile");
    } finally {
      setSavingProfile(false);
    }
  }

  /** Regenerate the macrocycle (used by equipment dialog) */
  async function handleRegenMacro() {
    setRegeneratingMacro(true);
    setActionError(null);
    try {
      await generateMacrocycle();
      await refresh();
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Regeneration failed"
      );
    } finally {
      setRegeneratingMacro(false);
    }
  }

  /** Full macrocycle restart from week 1 (Danger Zone) */
  async function handleRestartMacro() {
    setRestartingMacro(true);
    setActionError(null);
    try {
      await generateMacrocycle();
      await refresh();
      setRestartMacroConfirmOpen(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Restart failed");
      setRestartMacroConfirmOpen(false);
    } finally {
      setRestartingMacro(false);
    }
  }

  /** Full reset: double confirmation and redirect */
  async function handleReset() {
    setActionError(null);
    try {
      await deleteState();
      router.push("/onboarding/welcome");
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Reset failed"
      );
      setResetConfirmOpen(false);
    }
  }

  return (
    <>
      <TopBar title="Settings" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Loading error */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={refresh}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Action error */}
        {actionError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{actionError}</p>
          </div>
        )}

        {!loading && !error && state && (
          <>
            {/* ----- Profile ----- */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Profile</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setProfileEditorOpen(true)}
                  >
                    Edit
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <InfoRow
                  label="Name"
                  value={(user.name as string) || (user.preferred_name as string) || "—"}
                />
                <InfoRow
                  label="Weight"
                  value={(() => {
                    const w = assessment?.body?.weight_kg ?? body?.weight_kg ?? user.weight_kg;
                    return w != null ? `${w} kg` : "—";
                  })()}
                />
                <InfoRow
                  label="Height"
                  value={(() => {
                    const h = assessment?.body?.height_cm ?? body?.height_cm ?? user.height_cm;
                    return h != null ? `${h} cm` : "—";
                  })()}
                />
                <InfoRow
                  label="Lead RP"
                  value={(assessment?.grades?.lead_max_rp as string) || "—"}
                />
                {assessment?.grades?.boulder_max_rp && (
                  <InfoRow
                    label="Boulder RP"
                    value={assessment.grades.boulder_max_rp as string}
                  />
                )}
              </CardContent>
            </Card>

            {/* ----- Goal ----- */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Goal</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setGoalEditorOpen(true)}
                  >
                    Edit
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <InfoRow
                  label="Target grade"
                  value={(goal.target_grade as string) || "—"}
                />
                <InfoRow
                  label="Discipline"
                  value={(goal.discipline as string) || "—"}
                />
                <InfoRow
                  label="Deadline"
                  value={
                    goal.deadline
                      ? new Date(goal.deadline as string).toLocaleDateString(
                          "en-US",
                          { day: "numeric", month: "long", year: "numeric" }
                        )
                      : "—"
                  }
                />
                <InfoRow
                  label="Current grade"
                  value={(goal.current_grade as string) || "—"}
                />
              </CardContent>
            </Card>

            {/* ----- Equipment ----- */}
            {editingEquipment ? (
              <EquipmentEditor
                initialEquipment={equipment}
                onSave={handleSaveEquipment}
                onCancel={() => setEditingEquipment(false)}
              />
            ) : (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Equipment</CardTitle>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => setEditingEquipment(true)}
                    >
                      Edit
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {equipment.home_enabled && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        Home
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {equipment.home && equipment.home.length > 0
                          ? equipment.home.map((item) => (
                              <Badge
                                key={item}
                                variant="outline"
                                className="text-[10px]"
                              >
                                {item.replace(/_/g, " ")}
                              </Badge>
                            ))
                          : (
                              <span className="text-xs text-muted-foreground">
                                None
                              </span>
                            )}
                      </div>
                    </div>
                  )}
                  {equipment.gyms &&
                    equipment.gyms.map((gym, index) => (
                      <div key={`gym-${index}`} className="mb-2">
                        <p className="text-xs font-medium text-muted-foreground mb-1">
                          {gym.name || `Gym ${index + 1}`}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {gym.equipment.map((item) => (
                            <Badge
                              key={item}
                              variant="outline"
                              className="text-[10px]"
                            >
                              {item.replace(/_/g, " ")}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  {!equipment.home_enabled &&
                    (!equipment.gyms || equipment.gyms.length === 0) && (
                      <p className="text-xs text-muted-foreground">
                        No equipment configured
                      </p>
                    )}
                </CardContent>
              </Card>
            )}

            {/* ----- Injuries & Limitations ----- */}
            {editingLimitations ? (
              <LimitationsEditor
                initialLimitations={(state?.limitations ?? {}) as { active_flags?: string[]; details?: Array<{ area: string; side: string; severity: string; notes?: string }> }}
                onSave={handleSaveLimitations}
                onCancel={() => setEditingLimitations(false)}
              />
            ) : (
              <LimitationsSummary
                limitations={(state?.limitations ?? {}) as { active_flags?: string[]; details?: Array<{ area: string; side: string; severity: string; notes?: string }> }}
                onEdit={() => setEditingLimitations(true)}
              />
            )}

            {/* ----- Availability ----- */}
            {editingAvailability ? (
              <AvailabilityEditor
                initialAvailability={availability as Record<string, Record<string, { available: boolean; preferred_location: string; gym_id?: string }>>}
                initialPlanningPrefs={{
                  target_training_days_per_week: (state?.planning_prefs as Record<string, number>)?.target_training_days_per_week ?? 4,
                  hard_day_cap_per_week: (state?.planning_prefs as Record<string, number>)?.hard_day_cap_per_week ?? 3,
                }}
                gyms={equipment.gyms ?? []}
                onSave={handleSaveAvailability}
                onCancel={() => setEditingAvailability(false)}
              />
            ) : (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Availability</CardTitle>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => setEditingAvailability(true)}
                    >
                      Edit
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {Object.keys(availability).length > 0 ? (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      {Object.entries(availability).map(([day, slots]) => {
                        const slotEntries = slots ? Object.entries(slots) : [];
                        const availableSlots = slotEntries
                          .filter(([, s]) => s?.available)
                          .map(([slotName, s]) => {
                            const loc = s?.preferred_location;
                            if (!loc) return slotName;
                            if (loc === "home") return `${slotName} (home)`;
                            if (s?.gym_id) {
                              const gym = equipment.gyms?.find(
                                (g) => (g.gym_id || g.name) === s.gym_id
                              );
                              return `${slotName} (${gym?.name || s.gym_id})`;
                            }
                            return `${slotName} (gym)`;
                          });

                        return (
                          <div key={day} className="flex items-start gap-2 text-xs">
                            <span className="font-medium capitalize min-w-[60px]">
                              {day}
                            </span>
                            <span className="text-muted-foreground">
                              {availableSlots.length > 0
                                ? availableSlots.join(", ")
                                : "—"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      No availability configured
                    </p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* ----- Outdoor Spots ----- */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Outdoor Spots</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs text-primary"
                      onClick={() => router.push("/outdoor")}
                    >
                      View history
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => setAddingSpot(true)}
                    >
                      Add spot
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {outdoorSpots.length === 0 && !addingSpot && (
                  <p className="text-xs text-muted-foreground">
                    No outdoor spots saved yet
                  </p>
                )}
                {outdoorSpots.map((spot) => (
                  <div
                    key={spot.id}
                    className="flex items-center justify-between py-1.5 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{spot.name}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {spot.discipline}
                      </Badge>
                      {spot.typical_days && spot.typical_days.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {spot.typical_days.join(", ")}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteSpot(spot.id)}
                      className="text-xs text-destructive hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {addingSpot && (
                  <div className="mt-2 space-y-2 rounded-lg border p-3">
                    <input
                      type="text"
                      placeholder="Spot name"
                      value={newSpotName}
                      onChange={(e) => setNewSpotName(e.target.value)}
                      className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                    />
                    <div className="flex gap-2">
                      {(["boulder", "lead", "both"] as const).map((d) => (
                        <button
                          key={d}
                          onClick={() => setNewSpotDiscipline(d)}
                          className={`rounded-md px-3 py-1 text-xs border ${
                            newSpotDiscipline === d
                              ? "bg-primary text-primary-foreground"
                              : "bg-background"
                          }`}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleAddSpot}>
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setAddingSpot(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ----- Account ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Account</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Recovery code */}
                <div>
                  <p className="text-sm font-medium mb-1">Recovery code</p>
                  <p className="text-xs text-muted-foreground mb-3">
                    Use this code to recover your account if you lose access to this device.
                  </p>
                  {recoveryCode ? (
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-semibold tracking-widest bg-muted px-3 py-1.5 rounded-md">
                        {recoveryCode}
                      </span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(recoveryCode).then(() => {
                            setCodeCopied(true);
                            setTimeout(() => setCodeCopied(false), 2000);
                          });
                        }}
                        className="text-xs text-primary underline underline-offset-2"
                      >
                        {codeCopied ? "Copied!" : "Copy"}
                      </button>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={generatingCode}
                      onClick={handleGenerateCode}
                    >
                      {generatingCode ? "Generating..." : "Generate recovery code"}
                    </Button>
                  )}
                </div>

                <Separator />

                {/* Recover a different account */}
                <div>
                  <p className="text-sm font-medium mb-1">Recover a different account</p>
                  <p className="text-xs text-muted-foreground mb-3">
                    Enter a recovery code to switch to another account on this device.
                  </p>
                  {recoverInputOpen ? (
                    <div className="space-y-2">
                      <input
                        type="text"
                        placeholder="CLIMB-XXXX-XXXX"
                        value={recoverInput}
                        onChange={(e) => setRecoverInput(e.target.value.toUpperCase())}
                        onKeyDown={(e) => e.key === "Enter" && handleRecoverSubmit()}
                        className="w-full rounded-md border bg-background px-3 py-1.5 font-mono text-sm tracking-widest uppercase placeholder:normal-case placeholder:tracking-normal"
                        autoCapitalize="characters"
                        autoCorrect="off"
                        spellCheck={false}
                      />
                      {recoverError && (
                        <p className="text-xs text-destructive">{recoverError}</p>
                      )}
                      <div className="flex gap-2">
                        <Button size="sm" disabled={recovering || !recoverInput.trim()} onClick={handleRecoverSubmit}>
                          {recovering ? "Recovering..." : "Recover"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => { setRecoverInputOpen(false); setRecoverInput(""); setRecoverError(null); }}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setRecoverInputOpen(true)}
                    >
                      Enter recovery code
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* ----- Session preferences ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Session preferences</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Voice cues</p>
                    <p className="text-xs text-muted-foreground">
                      Speak phase transitions during guided sessions
                    </p>
                  </div>
                  <Switch
                    checked={voiceCuesOn}
                    onCheckedChange={(checked) => {
                      setVoiceCuesOn(checked);
                      setVoiceCuesEnabled(checked);
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            {/* ----- Backup & Restore ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Backup &amp; Restore</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Use backups to restore your data if you switch device or browser.
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={exporting}
                    onClick={async () => {
                      setExporting(true);
                      setBackupMsg(null);
                      try {
                        await exportUserState();
                        setBackupMsg({ type: "ok", text: "Backup downloaded" });
                      } catch {
                        setBackupMsg({ type: "err", text: "Export failed" });
                      } finally {
                        setExporting(false);
                      }
                    }}
                  >
                    {exporting ? "Exporting..." : "Export data"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={importing}
                    onClick={() => {
                      const input = document.createElement("input");
                      input.type = "file";
                      input.accept = ".json";
                      input.onchange = async () => {
                        const file = input.files?.[0];
                        if (!file) return;
                        setImporting(true);
                        setBackupMsg(null);
                        try {
                          const text = await file.text();
                          const data = JSON.parse(text);
                          await importUserState(data);
                          setBackupMsg({ type: "ok", text: "Data restored successfully" });
                          refresh();
                        } catch (e) {
                          const msg = e instanceof Error ? e.message : "Import failed";
                          setBackupMsg({ type: "err", text: msg });
                        } finally {
                          setImporting(false);
                        }
                      };
                      input.click();
                    }}
                  >
                    {importing ? "Importing..." : "Import data"}
                  </Button>
                </div>
                {backupMsg && (
                  <p className={`text-xs ${backupMsg.type === "ok" ? "text-green-500" : "text-destructive"}`}>
                    {backupMsg.text}
                  </p>
                )}
              </CardContent>
            </Card>

            <Separator />

            {/* ----- Danger zone ----- */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-destructive uppercase tracking-wider">
                Danger zone
              </h2>

              <Card className="border-destructive/30">
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Restart Macrocycle</p>
                    <p className="text-xs text-muted-foreground">
                      Discard the current plan and generate a new one from
                      week 1. Progression data is kept.
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setRestartMacroDialogOpen(true)}
                    disabled={restartingMacro}
                  >
                    {restartingMacro ? "Processing..." : "Restart"}
                  </Button>
                </CardContent>
              </Card>

              <Card className="border-destructive/30">
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Reset & Restart</p>
                    <p className="text-xs text-muted-foreground">
                      Delete all data and restart from onboarding.
                      This action is irreversible.
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setResetDialogOpen(true)}
                  >
                    Reset
                  </Button>
                </CardContent>
              </Card>
            </div>
          </>
        )}

        {/* ----- Debug info ----- */}
        {userId && (
          <p className="pb-4 text-center text-[10px] text-muted-foreground/40 font-mono">
            User ID: {userId}
          </p>
        )}
      </main>

      {/* ----- First restart macrocycle confirmation dialog ----- */}
      <Dialog open={restartMacroDialogOpen} onOpenChange={setRestartMacroDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Restart Macrocycle</DialogTitle>
            <DialogDescription>
              This will discard your entire current plan and generate a brand new
              macrocycle starting from week 1. All phase progress will be lost.
              Are you sure?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRestartMacroDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setRestartMacroDialogOpen(false);
                setRestartMacroConfirmOpen(true);
              }}
            >
              Yes, continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Second restart macrocycle confirmation dialog ----- */}
      <Dialog open={restartMacroConfirmOpen} onOpenChange={setRestartMacroConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Final confirmation</DialogTitle>
            <DialogDescription>
              The current macrocycle will be replaced with a new one starting
              from this Monday. This cannot be undone. Proceed?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRestartMacroConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRestartMacro}
              disabled={restartingMacro}
            >
              {restartingMacro ? "Processing..." : "Restart from week 1"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- First reset confirmation dialog ----- */}
      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reset & Restart</DialogTitle>
            <DialogDescription>
              You are about to delete all your training data, profile, and
              plan. This action is irreversible. Are you sure?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setResetDialogOpen(false);
                setResetConfirmOpen(true);
              }}
            >
              Yes, continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Second reset confirmation dialog ----- */}
      <Dialog open={resetConfirmOpen} onOpenChange={setResetConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Final confirmation</DialogTitle>
            <DialogDescription>
              Last chance: all data will be permanently deleted.
              It cannot be recovered. Confirm the reset?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleReset}>
              Delete everything
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Equipment saved dialog ----- */}
      <Dialog open={equipmentSavedOpen} onOpenChange={setEquipmentSavedOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Equipment updated</DialogTitle>
            <DialogDescription>
              Regenerate your plan to apply changes?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEquipmentSavedOpen(false)}
            >
              Keep current plan
            </Button>
            <Button
              onClick={() => {
                setEquipmentSavedOpen(false);
                handleRegenMacro();
              }}
              disabled={regeneratingMacro}
            >
              {regeneratingMacro ? "Processing..." : "Regenerate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Profile/assessment editor dialog ----- */}
      <ProfileAssessmentEditor
        open={profileEditorOpen}
        currentAssessment={assessment}
        onConfirm={handleProfileConfirm}
        onCancel={() => setProfileEditorOpen(false)}
        saving={savingProfile}
      />

      {/* ----- Goal editor dialog ----- */}
      <GoalEditor
        open={goalEditorOpen}
        currentGoal={goal}
        grades={(assessment?.grades ?? {}) as Record<string, string>}
        onConfirm={handleGoalConfirm}
        onCancel={() => setGoalEditorOpen(false)}
        saving={savingGoal}
      />
    </>
  );
}

/** Helper component for key-value information row */
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
