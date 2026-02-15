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

  // Dati utente
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

  /** Rigenera il profilo di assessment */
  async function handleRegenAssessment() {
    setRegeneratingAssessment(true);
    setActionError(null);
    try {
      await computeAssessment(state?.assessment, state?.goal);
      await refresh();
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Errore nella rigenerazione"
      );
    } finally {
      setRegeneratingAssessment(false);
    }
  }

  /** Rigenera il macrociclo (con conferma) */
  async function handleRegenMacro() {
    setRegeneratingMacro(true);
    setActionError(null);
    try {
      await generateMacrocycle();
      await refresh();
      setMacroDialogOpen(false);
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Errore nella rigenerazione"
      );
    } finally {
      setRegeneratingMacro(false);
    }
  }

  /** Reset totale: doppia conferma e redirect */
  async function handleReset() {
    setActionError(null);
    try {
      await deleteState();
      router.push("/onboarding/welcome");
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Errore nel reset"
      );
      setResetConfirmOpen(false);
    }
  }

  return (
    <>
      <TopBar title="Impostazioni" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Caricamento */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Errore caricamento */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={refresh}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Riprova
            </button>
          </div>
        )}

        {/* Errore azione */}
        {actionError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{actionError}</p>
          </div>
        )}

        {!loading && !error && state && (
          <>
            {/* ----- Profilo ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Profilo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <InfoRow
                  label="Nome"
                  value={(user.name as string) || (user.preferred_name as string) || "—"}
                />
                <InfoRow
                  label="Peso"
                  value={
                    user.weight_kg != null ? `${user.weight_kg} kg` : "—"
                  }
                />
                <InfoRow
                  label="Altezza"
                  value={
                    user.height_cm != null ? `${user.height_cm} cm` : "—"
                  }
                />
              </CardContent>
            </Card>

            {/* ----- Obiettivo ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Obiettivo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <InfoRow
                  label="Grado target"
                  value={(goal.target_grade as string) || "—"}
                />
                <InfoRow
                  label="Disciplina"
                  value={(goal.discipline as string) || "—"}
                />
                <InfoRow
                  label="Scadenza"
                  value={
                    goal.deadline
                      ? new Date(goal.deadline as string).toLocaleDateString(
                          "it-IT",
                          { day: "numeric", month: "long", year: "numeric" }
                        )
                      : "—"
                  }
                />
                <InfoRow
                  label="Grado attuale"
                  value={(goal.current_grade as string) || "—"}
                />
              </CardContent>
            </Card>

            {/* ----- Equipaggiamento ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Equipaggiamento</CardTitle>
              </CardHeader>
              <CardContent>
                {equipment.home_enabled && (
                  <div className="mb-2">
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Casa
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
                              Nessuno
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
                      Nessun equipaggiamento configurato
                    </p>
                  )}
              </CardContent>
            </Card>

            {/* ----- Disponibilita ----- */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Disponibilita</CardTitle>
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
                    Nessuna disponibilita configurata
                  </p>
                )}
              </CardContent>
            </Card>

            <Separator />

            {/* ----- Azioni ----- */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Azioni
              </h2>

              <Card>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Rigenera Assessment</p>
                    <p className="text-xs text-muted-foreground">
                      Ricalcola il profilo di valutazione su 6 assi
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRegenAssessment}
                    disabled={regeneratingAssessment}
                  >
                    {regeneratingAssessment ? "Elaborazione..." : "Rigenera"}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Rigenera Macrociclo</p>
                    <p className="text-xs text-muted-foreground">
                      Genera un nuovo piano periodizzato di allenamento
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setMacroDialogOpen(true)}
                    disabled={regeneratingMacro}
                  >
                    {regeneratingMacro ? "Elaborazione..." : "Rigenera"}
                  </Button>
                </CardContent>
              </Card>
            </div>

            <Separator />

            {/* ----- Zona pericolosa ----- */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-destructive uppercase tracking-wider">
                Zona pericolosa
              </h2>

              <Card className="border-destructive/30">
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium">Reset & Ricomincia</p>
                    <p className="text-xs text-muted-foreground">
                      Cancella tutti i dati e ricomincia dall&apos;onboarding.
                      Questa azione e irreversibile.
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

      {/* ----- Dialog conferma rigenerazione macrociclo ----- */}
      <Dialog open={macroDialogOpen} onOpenChange={setMacroDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rigenera macrociclo</DialogTitle>
            <DialogDescription>
              Questa azione sostituira il macrociclo attuale con uno nuovo.
              I dati di progressione verranno mantenuti, ma il piano settimanale
              cambiera. Vuoi procedere?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMacroDialogOpen(false)}
            >
              Annulla
            </Button>
            <Button onClick={handleRegenMacro} disabled={regeneratingMacro}>
              {regeneratingMacro ? "Elaborazione..." : "Conferma"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Dialog prima conferma reset ----- */}
      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reset & Ricomincia</DialogTitle>
            <DialogDescription>
              Stai per cancellare tutti i tuoi dati di allenamento, profilo e
              piano. Questa azione e irreversibile. Sei sicuro?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetDialogOpen(false)}
            >
              Annulla
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setResetDialogOpen(false);
                setResetConfirmOpen(true);
              }}
            >
              Si, continua
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----- Dialog seconda conferma reset ----- */}
      <Dialog open={resetConfirmOpen} onOpenChange={setResetConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Conferma definitiva</DialogTitle>
            <DialogDescription>
              Ultima possibilita: tutti i dati verranno eliminati definitivamente.
              Non sara possibile recuperarli. Confermi il reset?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetConfirmOpen(false)}
            >
              Annulla
            </Button>
            <Button variant="destructive" onClick={handleReset}>
              Elimina tutto
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Componente helper per riga informazione chiave-valore */
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
