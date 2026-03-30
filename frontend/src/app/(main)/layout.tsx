import { BottomNav } from "@/components/layout/bottom-nav";
import { TrialBanner } from "@/components/layout/trial-banner";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen pb-20">
      <TrialBanner />
      {children}
      <BottomNav />
    </div>
  );
}
