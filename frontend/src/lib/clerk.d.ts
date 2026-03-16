/* Clerk global type augmentation for window.Clerk.session.getToken() */
interface ClerkSession {
  getToken(): Promise<string | null>;
}

interface ClerkInstance {
  session: ClerkSession | null;
}

interface Window {
  Clerk?: ClerkInstance;
}
