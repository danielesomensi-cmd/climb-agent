"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { recoverAccount } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function RecoverPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRecover = async () => {
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const { uuid } = await recoverAccount(trimmed);
      localStorage.setItem("climb_user_id", uuid);
      router.push("/today");
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setError("Code not found. Check the code and try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Recover your account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Enter the recovery code you saved during onboarding (format:{" "}
            <span className="font-mono font-medium text-foreground">
              CLIMB-XXXX-XXXX
            </span>
            ) to restore access to your account on this device.
          </p>

          <input
            type="text"
            placeholder="CLIMB-XXXX-XXXX"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleRecover()}
            className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm tracking-widest uppercase placeholder:normal-case placeholder:tracking-normal"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
          />

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <Button
            className="w-full"
            disabled={loading || !code.trim()}
            onClick={handleRecover}
          >
            {loading ? "Recovering..." : "Recover account"}
          </Button>
        </CardContent>
      </Card>

      <div className="text-center">
        <button
          onClick={() => router.push("/onboarding/welcome")}
          className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          Back to welcome
        </button>
      </div>
    </div>
  );
}
