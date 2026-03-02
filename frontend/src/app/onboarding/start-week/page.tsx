"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getState, setStartWeek } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

export default function StartWeekPage() {
  const router = useRouter();
  const [maxOffset, setMaxOffset] = useState(0);
  const [selected, setSelected] = useState("0");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    getState().then((state) => {
      const dur = state.macrocycle?.phases?.[0]?.duration_weeks ?? 1;
      setMaxOffset(Math.min(dur - 1, 3));
      setReady(true);
    });
  }, []);

  const handleContinue = async () => {
    const offset = parseInt(selected, 10);
    setLoading(true);
    try {
      if (offset > 0) {
        await setStartWeek(offset);
      }
      router.push("/today");
    } catch {
      setLoading(false);
    }
  };

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Where do you want to start?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            If you&apos;ve already been following a structured training plan, you can
            skip ahead and start from a later week.
          </p>

          <RadioGroup value={selected} onValueChange={setSelected}>
            {Array.from({ length: maxOffset + 1 }, (_, i) => (
              <div key={i} className="flex items-center space-x-3 py-2">
                <RadioGroupItem value={String(i)} id={`week-${i}`} />
                <Label htmlFor={`week-${i}`} className="cursor-pointer">
                  {i === 0 ? "Start fresh — Week 1" : `Week ${i + 1}`}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          disabled={loading}
          onClick={() => router.push("/today")}
        >
          Skip
        </Button>
        <Button size="lg" disabled={loading} onClick={handleContinue}>
          {loading ? "Applying..." : "Continue"}
        </Button>
      </div>
    </div>
  );
}
