"use client";

import { TopBar } from "@/components/layout/top-bar";

export default function FreeSessionPage() {
  return (
    <>
      <TopBar title="Free Session" />
      <main className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-20">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <svg
              className="h-8 w-8 text-muted-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 11V6a2 2 0 00-2-2 2 2 0 00-2 2" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 10V4a2 2 0 00-2-2 2 2 0 00-2 2v2" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 10.5V6a2 2 0 00-2-2 2 2 0 00-2 2v8" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 8a2 2 0 012 2v7c0 3-2.5 5-5 5h-4c-2 0-4-1-5.5-2.5L2 16" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold">Coming soon</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            Build your own session from the exercise catalog. Pick exercises, set
            loads, and train freestyle.
          </p>
        </div>
      </main>
    </>
  );
}
