"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const AREAS = [
  { value: "gomito", label: "Gomito" },
  { value: "spalla", label: "Spalla" },
  { value: "polso", label: "Polso" },
  { value: "ginocchio", label: "Ginocchio" },
  { value: "schiena", label: "Schiena" },
];

const SIDES = [
  { value: "sinistro", label: "Sinistro" },
  { value: "destro", label: "Destro" },
  { value: "entrambi", label: "Entrambi" },
];

const SEVERITIES = [
  { value: "lieve", label: "Lieve" },
  { value: "moderato", label: "Moderato" },
  { value: "severo", label: "Severo" },
];

interface Limitation {
  area: string;
  side: string;
  severity: string;
  notes?: string;
}

export default function LimitationsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const limitations = data.limitations;

  const [hasLimitations, setHasLimitations] = useState(limitations.length > 0);

  const addLimitation = () => {
    update("limitations", [
      ...limitations,
      { area: "", side: "", severity: "", notes: "" },
    ]);
  };

  const removeLimitation = (index: number) => {
    const next = limitations.filter((_, i) => i !== index);
    update("limitations", next);
    if (next.length === 0) setHasLimitations(false);
  };

  const setField = (
    index: number,
    field: keyof Limitation,
    value: string,
  ) => {
    const next = limitations.map((l, i) =>
      i === index ? { ...l, [field]: value } : l,
    );
    update("limitations", next);
  };

  const toggleLimitations = (checked: boolean) => {
    setHasLimitations(checked);
    if (checked && limitations.length === 0) {
      update("limitations", [{ area: "", side: "", severity: "", notes: "" }]);
    }
    if (!checked) {
      update("limitations", []);
    }
  };

  // Valid if no limitations, or all have area+side+severity
  const isValid =
    !hasLimitations ||
    limitations.every((l) => l.area !== "" && l.side !== "" && l.severity !== "");

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            Hai infortuni o limitazioni attuali?
          </CardTitle>
          <CardDescription>
            Il piano evitera esercizi che aggravano le tue limitazioni
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-3">
            <Switch
              id="has-limitations"
              checked={hasLimitations}
              onCheckedChange={toggleLimitations}
            />
            <Label htmlFor="has-limitations">Si, ho qualcosa</Label>
          </div>

          {hasLimitations && (
            <>
              {limitations.map((lim, index) => (
                <div
                  key={index}
                  className="space-y-4 rounded-lg border p-4"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">
                      Limitazione {index + 1}
                    </p>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => removeLimitation(index)}
                    >
                      Rimuovi
                    </Button>
                  </div>

                  {/* Area */}
                  <div className="space-y-2">
                    <Label>Area</Label>
                    <Select
                      value={lim.area}
                      onValueChange={(v) => setField(index, "area", v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Seleziona area" />
                      </SelectTrigger>
                      <SelectContent>
                        {AREAS.map((a) => (
                          <SelectItem key={a.value} value={a.value}>
                            {a.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Side */}
                  <div className="space-y-2">
                    <Label>Lato</Label>
                    <Select
                      value={lim.side}
                      onValueChange={(v) => setField(index, "side", v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Seleziona lato" />
                      </SelectTrigger>
                      <SelectContent>
                        {SIDES.map((s) => (
                          <SelectItem key={s.value} value={s.value}>
                            {s.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Severity */}
                  <div className="space-y-2">
                    <Label>Gravita</Label>
                    <Select
                      value={lim.severity}
                      onValueChange={(v) => setField(index, "severity", v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Seleziona gravita" />
                      </SelectTrigger>
                      <SelectContent>
                        {SEVERITIES.map((s) => (
                          <SelectItem key={s.value} value={s.value}>
                            {s.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Notes */}
                  <div className="space-y-2">
                    <Label htmlFor={`notes-${index}`}>
                      Note (opzionale)
                    </Label>
                    <Input
                      id={`notes-${index}`}
                      value={lim.notes ?? ""}
                      onChange={(e) => setField(index, "notes", e.target.value)}
                      placeholder="Dettagli aggiuntivi..."
                    />
                  </div>
                </div>
              ))}

              <Button
                variant="outline"
                className="w-full"
                onClick={addLimitation}
              >
                Aggiungi altra limitazione
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/tests")}
        >
          Indietro
        </Button>
        <div className="flex gap-2">
          {hasLimitations && (
            <Button
              variant="ghost"
              onClick={() => {
                update("limitations", []);
                setHasLimitations(false);
                router.push("/onboarding/locations");
              }}
            >
              Salta
            </Button>
          )}
          <Button
            disabled={!isValid}
            onClick={() => router.push("/onboarding/locations")}
          >
            Avanti
          </Button>
        </div>
      </div>
    </div>
  );
}
