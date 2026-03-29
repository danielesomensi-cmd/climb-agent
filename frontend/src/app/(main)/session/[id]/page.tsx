"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { TopBar } from "@/components/layout/top-bar";
import { ExerciseCard } from "@/components/training/exercise-card";
import { resolveSession } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { ResolvedSession } from "@/lib/types";

/** Format session_id into a readable name */
function formatSessionName(sessionId: string): string {
  return sessionId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format rest seconds into a readable string */
function formatRest(seconds: number): string {
  if (seconds >= 60) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins} min`;
  }
  return `${seconds}s`;
}

function SessionPageInner() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded: authReady } = useAuth();
  const sessionId = typeof params.id === "string" ? params.id : "";
  const date = searchParams.get("date") || new Date().toISOString().slice(0, 10);

  const [resolved, setResolved] = useState<ResolvedSession | null>(null);
  const [rawInstances, setRawInstances] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSession = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await resolveSession(sessionId);
      setResolved(data.resolved);
      // Keep raw exercise instances for detail sheet
      const raw = data as unknown as Record<string, unknown>;
      const rs = (raw.resolved as Record<string, unknown> | undefined)?.resolved_session as Record<string, unknown> | undefined;
      setRawInstances((rs?.exercise_instances ?? []) as Record<string, unknown>[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // B155: gate on Clerk readiness
  useEffect(() => {
    if (!authReady) return;
    fetchSession();
  }, [fetchSession, authReady]);

  const displayName = (resolved as unknown as Record<string, Record<string, string>> | undefined)?.session?.session_name || formatSessionName(sessionId);

  return (
    <>
      <TopBar
        title={displayName}
        subtitle={sessionId.replace(/_/g, " ")}
        backHref="/today"
      />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={fetchSession}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Resolved session: blocks with exercises */}
        {!loading && !error && resolved && (
          <>
            {resolved.blocks.map((block, blockIdx) => (
              <div key={blockIdx} className="space-y-3">
                {/* Block header */}
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    Block {blockIdx + 1}
                  </Badge>
                  <span className="text-sm font-medium">
                    {block.block_name}
                  </span>
                </div>

                {/* Exercises in block */}
                <div className="space-y-2 pl-2 border-l-2 border-border">
                  {block.exercises.map((exercise, exIdx) => {
                    const rawMatch = rawInstances.find(
                      (r) => (r.exercise_id as string) === exercise.exercise_id,
                    );
                    return (
                      <ExerciseCard
                        key={`${blockIdx}-${exIdx}`}
                        exercise={exercise}
                        rawExercise={rawMatch}
                      />
                    );
                  })}
                </div>

                {/* Separator between blocks (except last) */}
                {blockIdx < resolved.blocks.length - 1 && (
                  <Separator className="my-2" />
                )}
              </div>
            ))}

            <Separator />

            {/* Rest timer placeholder */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Rest timer</CardTitle>
              </CardHeader>
              <CardContent className="text-center space-y-3">
                <div className="flex items-center justify-center">
                  <div className="flex items-center justify-center h-24 w-24 rounded-full border-4 border-primary/20">
                    <span className="text-2xl font-mono font-bold text-muted-foreground">
                      0:00
                    </span>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Rest timer between sets. Coming soon.
                </p>

                {/* Suggested rest times from exercises */}
                {resolved.blocks.some((b) =>
                  b.exercises.some((e) => e.rest_s != null)
                ) && (
                  <div className="mt-2 space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Suggested rest times
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {Array.from(
                        new Set(
                          resolved.blocks
                            .flatMap((b) => b.exercises)
                            .filter((e) => e.rest_s != null)
                            .map((e) => e.rest_s!)
                        )
                      )
                        .sort((a, b) => a - b)
                        .map((rest) => (
                          <Badge key={rest} variant="outline" className="text-xs">
                            {formatRest(rest)}
                          </Badge>
                        ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}

        {/* No session found */}
        {!loading && !error && !resolved && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              Session not found
            </p>
          </div>
        )}

        {/* Start guided session CTA */}
        {!loading && !error && resolved && (
          <div className="sticky bottom-20 pb-2">
            <Button
              className="w-full"
              size="lg"
              onClick={() => router.push(`/guided/${date}/${sessionId}`)}
            >
              Start Guided Session
            </Button>
          </div>
        )}
      </main>
    </>
  );
}

export default function SessionPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><p>Loading...</p></div>}>
      <SessionPageInner />
    </Suspense>
  );
}
