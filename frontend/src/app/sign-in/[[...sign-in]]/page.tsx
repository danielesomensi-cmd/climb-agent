import { SignIn } from "@clerk/nextjs";
import { ClerkGate } from "@/components/auth/clerk-gate";

export default function SignInPage() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      {/* B339 — without the gate this page is a black screen whenever Clerk's
          frontend API is unreachable (corporate network, VPN, ad-blocker). */}
      <ClerkGate>
        <SignIn />
      </ClerkGate>
    </div>
  );
}
