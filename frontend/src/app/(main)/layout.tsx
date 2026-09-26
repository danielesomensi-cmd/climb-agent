import { BottomNav } from "@/components/layout/bottom-nav";
import { TrialBanner } from "@/components/layout/trial-banner";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    /* A286 — l'altezza della nav ora è un token (--nav-h in globals.css):
       era ricopiata a mano qui e in altri tre file, con due copie sbagliate. */
    <div className="min-h-screen pb-[var(--nav-h)]">
      <TrialBanner />
      {children}
      <BottomNav />
    </div>
  );
}
