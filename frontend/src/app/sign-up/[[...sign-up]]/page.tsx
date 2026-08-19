import { SignUp } from "@clerk/nextjs";
import { ClerkGate } from "@/components/auth/clerk-gate";

export default function SignUpPage() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      {/* B339 — same black screen as /sign-in when Clerk cannot be reached. */}
      <ClerkGate>
        <SignUp />
      </ClerkGate>
    </div>
  );
}
