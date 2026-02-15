"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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

const LEAD_GRADES = [
  "5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

const BOULDER_GRADES = [
  "5A","5A+","5B","5B+","5C","5C+",
  "6A","6A+","6B","6B+","6C","6C+",
  "7A","7A+","7B","7B+","7C","7C+",
  "8A","8A+","8B","8B+","8C","8C+",
];

export default function GradesPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const grades = data.grades;

  const set = (field: keyof typeof grades, value: string) => {
    update("grades", { ...grades, [field]: value });
  };

  const isValid = grades.lead_max_rp !== "" && grades.lead_max_os !== "";

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">I tuoi gradi</CardTitle>
          <CardDescription>
            La differenza tra redpoint e onsight ci dice molto sulla tua power
            endurance e tecnica
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Lead Redpoint */}
          <div className="space-y-2">
            <Label>Lead Redpoint *</Label>
            <p className="text-xs text-muted-foreground">
              Il grado piu alto che hai chiuso lavorandoci
            </p>
            <Select
              value={grades.lead_max_rp}
              onValueChange={(v) => set("lead_max_rp", v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleziona grado" />
              </SelectTrigger>
              <SelectContent>
                {LEAD_GRADES.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Lead Onsight */}
          <div className="space-y-2">
            <Label>Lead Onsight *</Label>
            <p className="text-xs text-muted-foreground">
              Il grado che riesci a fare a vista
            </p>
            <Select
              value={grades.lead_max_os}
              onValueChange={(v) => set("lead_max_os", v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleziona grado" />
              </SelectTrigger>
              <SelectContent>
                {LEAD_GRADES.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Boulder Redpoint */}
          <div className="space-y-2">
            <Label>Boulder Redpoint</Label>
            <p className="text-xs text-muted-foreground">
              Il tuo grado boulder massimo
            </p>
            <Select
              value={grades.boulder_max_rp ?? ""}
              onValueChange={(v) => set("boulder_max_rp", v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleziona grado (opzionale)" />
              </SelectTrigger>
              <SelectContent>
                {BOULDER_GRADES.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Boulder Onsight */}
          <div className="space-y-2">
            <Label>Boulder Onsight</Label>
            <p className="text-xs text-muted-foreground">
              Il grado boulder che fai a vista/flash
            </p>
            <Select
              value={grades.boulder_max_os ?? ""}
              onValueChange={(v) => set("boulder_max_os", v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleziona grado (opzionale)" />
              </SelectTrigger>
              <SelectContent>
                {BOULDER_GRADES.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/experience")}
        >
          Indietro
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/goals")}
        >
          Avanti
        </Button>
      </div>
    </div>
  );
}
