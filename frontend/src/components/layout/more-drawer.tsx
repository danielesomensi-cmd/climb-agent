"use client";

import Link from "next/link";
import {
  Drawer,
  DrawerContent,
  DrawerClose,
  DrawerTitle,
} from "@/components/ui/drawer";

export type MoreNavItem = { href: string; label: string; icon: string };

/**
 * B398 (O10) — the bottom nav's "More" drawer, in its own module so the drawer
 * library (vaul) loads off the first paint: BottomNav imports it with
 * next/dynamic and mounts it on idle (or on the first tap on More). Markup and
 * behaviour are the ones that lived inline in bottom-nav.tsx.
 */
export function MoreDrawer({
  open,
  onOpenChange,
  pathname,
  items,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pathname: string;
  items: readonly MoreNavItem[];
}) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      {/* A310 — senza un titolo il dialog era senza nome per VoiceOver (e
          Radix lo segnala in console); nessuna descrizione da collegare. */}
      <DrawerContent aria-describedby={undefined}>
        <DrawerTitle className="sr-only">More</DrawerTitle>
        {/* A286 — l'ultima riga di icone finiva sotto l'home indicator su
            iPhone: pb-6 fisso non tiene conto della safe area. */}
        <div className="p-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
          <div className="grid grid-cols-3 gap-3">
            {items.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <DrawerClose key={item.href} asChild>
                  <Link
                    href={item.href}
                    className={`flex min-h-[72px] flex-col items-center justify-center gap-2 rounded-xl p-3 transition-colors ${
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                  >
                    <svg
                      className="h-6 w-6"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={active ? 2.5 : 1.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={item.icon}
                      />
                    </svg>
                    <span className="text-xs font-medium">{item.label}</span>
                  </Link>
                </DrawerClose>
              );
            })}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
