"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getState, setStartWeek, generateRecoveryCode } from "@/lib/api";
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

  // Recovery code modal state
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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
      // Generate recovery code before going to /today
      const { recovery_code } = await generateRecoveryCode();
      setRecoveryCode(recovery_code);
    } catch {
      // If recovery code generation fails, go to /today anyway
      router.push("/today");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!recoveryCode) return;
    navigator.clipboard.writeText(recoveryCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!ready) return null;

  // Recovery code modal — shown after plan is generated
  if (recoveryCode) {
    return (
      <div className="mx-auto max-w-lg space-y-6 pt-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Save your recovery code</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted-foreground">
              This code lets you recover your account if you lose access to this
              device — for example if you clear your browser data or switch
              phones.
            </p>

            {/* Code display */}
            <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-primary/30 bg-primary/5 py-6">
              <p className="font-mono text-2xl font-bold tracking-widest text-primary">
                {recoveryCode}
              </p>
              <button
                onClick={handleCopy}
                className="text-sm font-medium text-primary underline underline-offset-2"
              >
                {copied ? "Copied!" : "Copy to clipboard"}
              </button>
            </div>

            <p className="text-sm text-muted-foreground">
              Write it down or save it somewhere safe. You can also view it
              later in{" "}
              <span className="font-medium text-foreground">
                Settings → Account
              </span>
              .
            </p>

            <Button
              size="lg"
              className="w-full"
              onClick={() => router.push("/today")}
            >
              I&apos;ve saved my code — continue
            </Button>

            {/* Skip — small secondary text */}
            <div className="text-center">
              <button
                onClick={() => router.push("/today")}
                className="text-xs text-muted-foreground/60 underline underline-offset-2 hover:text-muted-foreground"
              >
                Skip for now
              </button>
              <p className="mt-1 text-[11px] text-muted-foreground/50">
                Without this code you won&apos;t be able to recover your account
                if you lose access to this device.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

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
