"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getState } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getState()
      .then((state) => {
        if (state.macrocycle) {
          router.replace("/today");
        } else {
          router.replace("/onboarding/welcome");
        }
      })
      .catch(() => {
        router.replace("/onboarding/welcome");
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }
  return null;
}
