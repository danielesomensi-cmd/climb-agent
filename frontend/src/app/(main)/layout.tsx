import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { BottomNav } from "@/components/layout/bottom-nav";

export default async function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { userId } = await auth();
  if (!userId) redirect("/sign-in");

  return (
    <div className="min-h-screen pb-20">
      {children}
      <BottomNav />
    </div>
  );
}
