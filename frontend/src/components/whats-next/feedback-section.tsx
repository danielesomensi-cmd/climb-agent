"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const FEEDBACK_EMAIL = "daniele.somensi@gmail.com";

export function FeedbackSection() {
  const [working, setWorking] = useState("");
  const [missing, setMissing] = useState("");
  const [contact, setContact] = useState("");

  function handleSend() {
    const lines: string[] = [];
    if (working.trim()) lines.push(`What's working well:\n${working.trim()}`);
    if (missing.trim()) lines.push(`What's missing or broken:\n${missing.trim()}`);
    if (contact.trim()) lines.push(`From: ${contact.trim()}`);

    if (lines.length === 0) return;

    const body = encodeURIComponent(lines.join("\n\n"));
    const subject = encodeURIComponent("Climb Agent Beta Feedback");
    window.location.href = `mailto:${FEEDBACK_EMAIL}?subject=${subject}&body=${body}`;
  }

  const hasContent = working.trim() || missing.trim();

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Help us improve</h2>
        <p className="text-sm text-muted-foreground">Your feedback shapes the next version</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="fb-working">What&apos;s working well?</Label>
          <textarea
            id="fb-working"
            rows={3}
            value={working}
            onChange={(e) => setWorking(e.target.value)}
            placeholder="Anything you enjoy so far..."
            className="placeholder:text-muted-foreground dark:bg-input/30 border-input w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-none"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="fb-missing">What&apos;s missing or broken?</Label>
          <textarea
            id="fb-missing"
            rows={3}
            value={missing}
            onChange={(e) => setMissing(e.target.value)}
            placeholder="Bugs, missing features, rough edges..."
            className="placeholder:text-muted-foreground dark:bg-input/30 border-input w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-none"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="fb-contact">Your name or email (optional)</Label>
          <Input
            id="fb-contact"
            type="text"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            placeholder="So we can follow up"
          />
        </div>

        <Button onClick={handleSend} disabled={!hasContent} className="w-full">
          <Send className="h-4 w-4" />
          Send feedback
        </Button>

        <p className="text-xs text-muted-foreground text-center">
          Opens your email app. If it doesn&apos;t work, write to{" "}
          <a href={`mailto:${FEEDBACK_EMAIL}`} className="text-primary underline">
            {FEEDBACK_EMAIL}
          </a>
        </p>
      </div>
    </section>
  );
}
