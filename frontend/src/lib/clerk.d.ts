/* Clerk global type augmentation for window.Clerk.session.getToken() */
interface ClerkSession {
  getToken(): Promise<string | null>;
}

interface ClerkUser {
  id: string;
}

interface ClerkInstance {
  session: ClerkSession | null;
  /** A245 B-2 — real user id, used to scope every persisted-cache key. */
  user?: ClerkUser | null;
  /** True once Clerk has finished bootstrapping on the client. */
  loaded?: boolean;
}

interface Window {
  Clerk?: ClerkInstance;
}
