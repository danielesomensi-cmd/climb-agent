"use client";

import { TopBar } from "@/components/layout/top-bar";
import { Separator } from "@/components/ui/separator";
import { RoadmapSection } from "@/components/whats-next/roadmap-section";
import { FeedbackSection } from "@/components/whats-next/feedback-section";

export default function WhatsNextPage() {
  return (
    <>
      <TopBar title="What's next" />

      <main className="mx-auto max-w-2xl space-y-8 p-4">
        <RoadmapSection />
        <Separator />
        <FeedbackSection />
      </main>
    </>
  );
}
