"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Check,
  Copy,
  Download,
  ExternalLink,
  MoreHorizontal,
  MoreVertical,
  PlusCircle,
  Share,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useInstall } from "@/lib/hooks/use-install";
import { getIosBrowser, getPlatform, getSafariMajorVersion } from "@/lib/install";
import { trackEvent } from "@/lib/analytics";

/* iOS share glyph — the square-with-up-arrow Safari puts in its toolbar.
   Lucide's Share is a different mark and users scan for this exact shape. */
function IosShareIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" />
      <polyline points="12 3 12 15" />
      <polyline points="8 7 12 3 16 7" />
    </svg>
  );
}

function Step({
  n,
  icon,
  title,
  children,
}: {
  n: number;
  icon: React.ReactNode;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex gap-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-bold text-primary">
        {n}
      </div>
      <div className="space-y-1 pt-0.5">
        <div className="flex items-center gap-2 text-foreground">{icon}</div>
        <p className="text-sm font-medium text-foreground">{title}</p>
        {children ? (
          <p className="text-sm text-muted-foreground">{children}</p>
        ) : null}
      </div>
    </li>
  );
}

/**
 * A260 — one card that adapts to what the current browser can actually do.
 *
 * The old screen showed a static iPhone/Android tab pair with iPhone hardcoded
 * as the default, so an Android user read Safari steps until they noticed the
 * tab, and someone arriving from an Instagram webview read steps they could not
 * perform at all. Each branch below is a different *possible action*, not a
 * different skin: install now, follow menu steps, or leave this browser first.
 */
export function InstallCard({ onDone }: { onDone?: () => void }) {
  const { capability, install } = useInstall();
  const [copied, setCopied] = useState(false);
  const tracked = useRef<string | null>(null);

  // One impression event per capability, so the funnel shows *where* people
  // land — an install rate is meaningless without knowing how many arrived in
  // a browser that cannot install.
  useEffect(() => {
    if (!capability || tracked.current === capability) return;
    tracked.current = capability;
    trackEvent("install_prompt_shown", {
      capability,
      platform: getPlatform(),
    });
  }, [capability]);

  // Pre-hydration: capability is unknown and any guess would be wrong for
  // someone. Reserve the space, show nothing.
  if (!capability) return <div className="min-h-[220px]" aria-busy="true" />;

  if (capability === "installed") {
    return (
      <div className="space-y-6">
        <div className="flex items-start gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
          <Check className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">
              You&apos;re all set
            </p>
            <p className="text-sm text-muted-foreground">
              climb-agent is installed on this device. It opens full-screen and
              works offline during a session.
            </p>
          </div>
        </div>
        {onDone ? (
          <Button className="min-h-[44px] w-full" onClick={onDone}>
            Continue
          </Button>
        ) : null}
      </div>
    );
  }

  if (capability === "native-prompt") {
    return (
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Install climb-agent on this device — it opens full-screen, keeps your
          plan available offline, and starts instantly from your home screen.
        </p>
        <Button
          className="min-h-[52px] w-full text-base"
          onClick={async () => {
            const outcome = await install();
            if (outcome === "accepted") {
              toast.success("Installing — check your home screen");
            }
          }}
        >
          <Download className="mr-2 h-5 w-5" />
          Install the app
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          One tap. Your browser will ask you to confirm.
        </p>
        {onDone ? (
          <Button
            variant="ghost"
            className="min-h-[44px] w-full"
            onClick={onDone}
          >
            Maybe later
          </Button>
        ) : null}
      </div>
    );
  }

  if (capability === "in-app-browser") {
    // Instagram/Facebook/LinkedIn webviews cannot install a PWA. Copying the
    // link is the shortest real path out: paste into Safari or Chrome, then the
    // normal flow applies.
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-sm font-medium text-foreground">
            Open this in your browser first
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            You&apos;re in an in-app browser (Instagram, Facebook or similar),
            which can&apos;t install apps. Copy the link and open it in Safari or
            Chrome.
          </p>
        </div>
        <Button
          className="min-h-[52px] w-full text-base"
          onClick={async () => {
            const url = window.location.origin;
            try {
              await navigator.clipboard.writeText(url);
              setCopied(true);
              toast.success("Link copied — paste it in Safari or Chrome");
              trackEvent("install_copy_link");
            } catch {
              toast.error(`Copy this address: ${url}`);
            }
          }}
        >
          {copied ? (
            <Check className="mr-2 h-5 w-5" />
          ) : (
            <Copy className="mr-2 h-5 w-5" />
          )}
          {copied ? "Link copied" : "Copy link"}
        </Button>
        <p className="flex items-center justify-center gap-1.5 text-center text-xs text-muted-foreground">
          <ExternalLink className="h-3.5 w-3.5" />
          Some apps also offer &quot;Open in browser&quot; in their menu.
        </p>
        {onDone ? (
          <Button
            variant="ghost"
            className="min-h-[44px] w-full"
            onClick={onDone}
          >
            Skip for now
          </Button>
        ) : null}
      </div>
    );
  }

  if (capability === "ios-manual") {
    const browser = getIosBrowser();
    const isChrome = browser === "chrome";
    // B316: iOS 26 hid Safari's Share button inside the ••• menu, so the
    // pre-26 wording sent people hunting for a toolbar icon that is no longer
    // there (reported from a real device).
    //
    // B317: and the version must come from `Version/nn`, NOT from the OS token
    // — Apple freezes that at `18_6` on iOS 26, so reading it turned this check
    // off on precisely the devices it targets. Null → assume the new layout;
    // step 1 names the alternative anyway, which also covers the Bottom/Top
    // toolbar layouts a user can still choose on iOS 26.
    const safariMajor = getSafariMajorVersion();
    const safariHidesShare = !isChrome && (safariMajor === null || safariMajor >= 26);
    return (
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          iOS doesn&apos;t let a website install itself — it takes a few taps in
          the {isChrome ? "Chrome" : "Safari"} menu.
        </p>
        <ol className="space-y-5">
          {safariHidesShare ? (
            <Step
              n={1}
              icon={<MoreHorizontal className="h-6 w-6" />}
              title="Tap the ••• button next to the address bar"
            >
              iOS 26 moved Share inside this menu — it is no longer an icon in
              the toolbar. If your Safari still shows the Share icon directly,
              tap that instead.
            </Step>
          ) : (
            <Step
              n={1}
              icon={<IosShareIcon className="h-6 w-6" />}
              title="Tap the Share button"
            >
              {isChrome
                ? "In Chrome it's in the address bar, top-right corner."
                : "It's the square-with-an-arrow icon in the bottom toolbar."}
            </Step>
          )}
          <Step
            n={2}
            icon={<IosShareIcon className="h-6 w-6" />}
            title={safariHidesShare ? "Tap Share, then scroll down" : "Scroll the share sheet down"}
          >
            The list is long: scroll past the apps and the first actions. If you
            don&apos;t see &quot;Add to Home Screen&quot;, tap &quot;More&quot;
            (or &quot;Edit Actions&quot;) at the bottom of the list.
          </Step>
          <Step
            n={3}
            icon={
              <div className="flex items-center gap-2">
                <PlusCircle className="h-6 w-6" />
                <span className="text-muted-foreground">&rarr;</span>
                <Check className="h-6 w-6" />
              </div>
            }
            title={'Tap "Add to Home Screen", then Add'}
          >
            From then on climb-agent opens full-screen, like any other app.
          </Step>
        </ol>
        {onDone ? (
          <Button className="min-h-[44px] w-full" onClick={onDone}>
            Continue
          </Button>
        ) : null}
      </div>
    );
  }

  // "unsupported": desktop browsers with no prompt yet, or Firefox on iOS,
  // which has no Add to Home Screen at all. Say what is true instead of
  // handing out steps that dead-end.
  const platform = getPlatform();
  const isFirefoxIos = platform === "ios" && getIosBrowser() === "firefox";
  return (
    <div className="space-y-6">
      {isFirefoxIos ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-sm font-medium text-foreground">
            Firefox on iOS can&apos;t add apps to the home screen
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Open climbagent.app in Safari and the Share menu will offer
            &quot;Add to Home Screen&quot;.
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            You can install climb-agent from your browser&apos;s menu — it then
            opens in its own window and works offline.
          </p>
          <ol className="space-y-5">
            <Step
              n={1}
              icon={<MoreVertical className="h-6 w-6" />}
              title="Open the browser menu"
            >
              Chrome and Edge: the three-dot menu. On desktop, look for an
              install icon at the right edge of the address bar.
            </Step>
            <Step
              n={2}
              icon={<Share className="h-6 w-6" />}
              title={'Choose "Install" or "Add to Home screen"'}
            >
              The wording differs by browser; both do the same thing.
            </Step>
          </ol>
        </>
      )}
      {onDone ? (
        <Button className="min-h-[44px] w-full" onClick={onDone}>
          Continue
        </Button>
      ) : null}
    </div>
  );
}
