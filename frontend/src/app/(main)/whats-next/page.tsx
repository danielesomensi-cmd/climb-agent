"use client";

import { TopBar } from "@/components/layout/top-bar";
import { Separator } from "@/components/ui/separator";
import { RoadmapSection } from "@/components/whats-next/roadmap-section";
import { FeedbackSection } from "@/components/whats-next/feedback-section";

export default function WhatsNextPage() {
  return (
    <>
      <TopBar title="Roadmap & Support" />

      <main className="mx-auto max-w-2xl space-y-8 p-4">
        <RoadmapSection />
        <Separator />
        <FeedbackSection />
        <p className="text-center text-xs text-muted-foreground pt-4">
          Thanks to our beta testers: Christie, Vato &amp; Alexis
        </p>
      </main>
    </>
  );
}
