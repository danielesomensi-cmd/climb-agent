import { BottomNav } from "@/components/layout/bottom-nav";
import { TrialBanner } from "@/components/layout/trial-banner";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen pb-[calc(3.5rem+env(safe-area-inset-bottom))]">
      <TrialBanner />
      {children}
      <BottomNav />
    </div>
  );
}
