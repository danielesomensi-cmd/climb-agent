"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { useUserState } from "@/lib/hooks/use-state";
import { computeAssessment, generateMacrocycle, deleteState } from "@/lib/api";
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

export default function SettingsPage() {
  const { state, loading, error, refresh } = useUserState();
  const router = useRouter();

  const [regeneratingAssessment, setRegeneratingAssessment] = useState(false);
  const [regeneratingMacro, setRegeneratingMacro] = useState(false);
  const [macroDialogOpen, setMacroDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // User data
  const user = state?.user ?? {};
  const goal = state?.goal ?? {};
  const equipment = (state?.equipment ?? {}) as {
    home_enabled?: boolean;
    home?: string[];
    gyms?: Array<{ name: string; equipment: string[] }>;
  };
  const availability = (state?.availability ?? {}) as Record<
    string,
    Record<string, { available: boolean }>
  >;

  /** Regenerate the assessment profile */
  async function handleRegenAssessment() {
    setRegeneratingAssessment(true);
    setActionError(null);
    try {
      await computeAssessment(state?.assessment, state?.goal);
      await refresh();
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Regeneration failed"
      );
    } finally {
      setRegeneratingAssessment(false);
    }
  }

  /** Regenerate the macrocycle (with confirmation) */
  async function handleRegenMacro() {
    setRegeneratingMacro(true);
    setActionError(null);
    try {
      await generateMacrocycle();
      await refresh();
      setMacroDialogOpen(false);
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Regeneration failed"
      );
    } finally {
      setRegeneratingMacro(false);
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
                <CardTitle className="text-base">Profile</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <InfoRow
                  label="Name"
                  value={(user.name as string) || (user.preferred_name as string) || "—"}
                />
                <InfoRow
                  label="Weight"
                  value={
                    user.weight_kg != null ? `${user.weight_kg} kg` : "—"
                  }
                />
                <InfoRow
                  label="Height"
                  value={
                    user.height_cm != null ? `${user.height_cm} cm` : "—"
                  }
                />
              </CardContent>
            </Card>

            {/* ----- Goal ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Goal</CardTitle>
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
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Equipment</CardTitle>
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
                  equipment.gyms.map((gym) => (
                    <div key={gym.name} className="mb-2">
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        {gym.name}
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

            {/* ----- Availability ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Availability</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(availability).length > 0 ? (
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    {Object.entries(availability).map(([day, slots]) => {
                      const slotEntries = slots ? Object.entries(slots) : [];
                      const availableSlots = slotEntries
                        .filter(([, s]) => s?.available)
                        .map(([slotName]) => slotName);

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

            <Separator />

            {/* ----- Actions ----- */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Actions
              </h2>

              <Card>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Regenerate Assessment</p>
                    <p className="text-xs text-muted-foreground">
                      Recalculate the 6-axis assessment profile
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRegenAssessment}
                    disabled={regeneratingAssessment}
                  >
                    {regeneratingAssessment ? "Processing..." : "Regenerate"}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Regenerate Macrocycle</p>
                    <p className="text-xs text-muted-foreground">
                      Generate a new periodized training plan
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setMacroDialogOpen(true)}
                    disabled={regeneratingMacro}
                  >
                    {regeneratingMacro ? "Processing..." : "Regenerate"}
                  </Button>
                </CardContent>
              </Card>
            </div>

            <Separator />

            {/* ----- Danger zone ----- */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-destructive uppercase tracking-wider">
                Danger zone
              </h2>

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
      </main>

      {/* ----- Macrocycle regeneration confirmation dialog ----- */}
      <Dialog open={macroDialogOpen} onOpenChange={setMacroDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Regenerate macrocycle</DialogTitle>
            <DialogDescription>
              This will replace the current macrocycle with a new one.
              Progression data will be kept, but the weekly plan will change.
              Proceed?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMacroDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleRegenMacro} disabled={regeneratingMacro}>
              {regeneratingMacro ? "Processing..." : "Confirm"}
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
