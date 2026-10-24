"use client";

import { useRef, useState } from "react";
import { Route, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { getQuaderno, quadernoPageUrl } from "@/lib/api";
import { formatDateShort } from "@/lib/format";

/**
 * A321 — "Topo & charts": the athlete's quaderno (route drawings, per-second
 * charts, beta), opened on one crag day.
 *
 * climb-agent draws nothing here: the page is the athlete's own report, hosted
 * by the backend and shown in a sandboxed iframe (scripts only — an opaque
 * origin with no cookies, no storage, no access to this app). The frame fills
 * the viewport and scrolls inside itself: the page sizes its drawings from its
 * own window height, so a content-tall frame would blow them up.
 *
 * Each opening asks the backend for a freshly signed link, so a page left open
 * for hours never hands the iframe an expired one.
 */
export function QuadernoButton({ date }: { date: string }) {
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  // Only the latest opening may set the frame (close + reopen while a link is
  // still being signed must not show the older answer).
  const request = useRef(0);

  async function openViewer() {
    const id = ++request.current;
    setOpen(true);
    setSrc(null);
    setFailed(false);
    setLoaded(false);
    try {
      const info = await getQuaderno();
      if (id !== request.current) return;
      if (info.available && info.days.includes(date)) {
        setSrc(quadernoPageUrl(info.page_path, date));
      } else {
        setFailed(true);
      }
    } catch {
      if (id === request.current) setFailed(true);
    }
  }

  function onOpenChange(next: boolean) {
    if (!next) {
      request.current += 1;
      setSrc(null);
    }
    setOpen(next);
  }

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        className="min-h-[44px] text-xs text-success border-success/30 hover:bg-success/15 hover:text-success"
        onClick={openViewer}
      >
        <Route className="size-3.5 mr-1" />
        Topo &amp; charts
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          showCloseButton={false}
          className="top-0 left-0 flex h-[100dvh] w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 rounded-none border-0 p-0 sm:max-w-none data-[state=closed]:zoom-out-100 data-[state=open]:zoom-in-100"
        >
          <div className="flex items-center gap-2 border-b border-border px-3 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
            <Route className="size-4 text-success" />
            <DialogTitle className="text-sm font-medium">
              Topo &amp; charts · {formatDateShort(date)}
            </DialogTitle>
            <DialogDescription className="sr-only">
              Your route report for this crag day: drawings, charts and beta.
            </DialogDescription>
            <Button
              size="icon"
              variant="ghost"
              className="ml-auto size-11"
              onClick={() => onOpenChange(false)}
              aria-label="Close"
            >
              <X className="size-5" />
            </Button>
          </div>
          <div className="relative min-h-0 flex-1 bg-background">
            {src && (
              <iframe
                key={src}
                src={src}
                title={`Topo and charts, ${date}`}
                sandbox="allow-scripts"
                referrerPolicy="no-referrer"
                className="absolute inset-0 h-full w-full border-0"
                onLoad={() => setLoaded(true)}
              />
            )}
            {!loaded && !failed && (
              <p className="absolute inset-x-0 top-8 text-center text-sm text-muted-foreground" role="status">
                Opening…
              </p>
            )}
            {failed && (
              <div className="absolute inset-x-0 top-8 space-y-3 px-6 text-center text-sm text-muted-foreground" role="alert">
                <p>Couldn&apos;t open the report for this day.</p>
                <Button size="sm" variant="outline" className="min-h-[44px]" onClick={openViewer}>
                  Try again
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
