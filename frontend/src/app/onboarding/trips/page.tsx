"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

const DISCIPLINES = [
  { value: "lead", label: "Lead" },
  { value: "boulder", label: "Boulder" },
];

const PRIORITIES = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

interface Trip {
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  priority: string;
}

export default function TripsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const trips = data.trips;

  const addTrip = () => {
    update("trips", [
      ...trips,
      { name: "", start_date: "", end_date: "", discipline: "lead", priority: "medium" },
    ]);
  };

  const removeTrip = (index: number) => {
    update("trips", trips.filter((_, i) => i !== index));
  };

  const setField = (index: number, field: keyof Trip, value: string) => {
    const next = trips.map((t, i) => {
      if (i !== index) return t;
      const updated = { ...t, [field]: value };
      // Auto-adjust end_date when start_date changes and end_date is before new start
      if (field === "start_date" && updated.end_date && updated.end_date <= value) {
        const d = new Date(value);
        d.setDate(d.getDate() + 1);
        updated.end_date = d.toISOString().split("T")[0];
      }
      return updated;
    });
    update("trips", next);
  };

  // Valid if no trips, or all trips have required fields and dates are valid
  const isValid =
    trips.length === 0 ||
    trips.every(
      (t) =>
        t.name.trim() !== "" &&
        t.start_date !== "" &&
        t.end_date !== "" &&
        t.end_date > t.start_date &&
        t.discipline !== "" &&
        t.priority !== "",
    );

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            Do you have outdoor trips planned?
          </CardTitle>
          <CardDescription>
            If you have a crag trip planned, the plan will automatically
            deload the days before
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {trips.map((trip, index) => (
            <div key={index} className="space-y-4 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">Trip {index + 1}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  onClick={() => removeTrip(index)}
                >
                  Remove
                </Button>
              </div>

              {/* Name */}
              <div className="space-y-2">
                <Label htmlFor={`trip-name-${index}`}>Name / Destination</Label>
                <Input
                  id={`trip-name-${index}`}
                  value={trip.name}
                  onChange={(e) => setField(index, "name", e.target.value)}
                  placeholder="E.g.: Arco, Kalymnos..."
                />
              </div>

              {/* Dates */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor={`trip-start-${index}`}>Start date</Label>
                  <Input
                    id={`trip-start-${index}`}
                    type="date"
                    value={trip.start_date}
                    onChange={(e) =>
                      setField(index, "start_date", e.target.value)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`trip-end-${index}`}>End date</Label>
                  <Input
                    id={`trip-end-${index}`}
                    type="date"
                    value={trip.end_date}
                    min={trip.start_date || undefined}
                    onChange={(e) =>
                      setField(index, "end_date", e.target.value)
                    }
                  />
                  {trip.start_date && trip.end_date && trip.end_date <= trip.start_date && (
                    <p className="text-xs text-red-500">
                      End date must be after start date
                    </p>
                  )}
                </div>
              </div>

              {/* Discipline */}
              <div className="space-y-2">
                <Label>Discipline</Label>
                <Select
                  value={trip.discipline}
                  onValueChange={(v) => setField(index, "discipline", v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select discipline" />
                  </SelectTrigger>
                  <SelectContent>
                    {DISCIPLINES.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Priority */}
              <div className="space-y-2">
                <Label>Priority</Label>
                <Select
                  value={trip.priority}
                  onValueChange={(v) => setField(index, "priority", v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select priority" />
                  </SelectTrigger>
                  <SelectContent>
                    {PRIORITIES.map((p) => (
                      <SelectItem key={p.value} value={p.value}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ))}

          <Button variant="outline" className="w-full" onClick={addTrip}>
            Add trip
          </Button>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/availability")}
        >
          Back
        </Button>
        <div className="flex gap-2">
          {trips.length === 0 && (
            <Button
              variant="ghost"
              onClick={() => router.push("/onboarding/review")}
            >
              No trips planned
            </Button>
          )}
          <Button
            disabled={!isValid}
            onClick={() => router.push("/onboarding/review")}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
