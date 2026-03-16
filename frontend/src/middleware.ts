import { clerkMiddleware } from "@clerk/nextjs/server";

// Use Clerk's default middleware — attaches auth context to all requests.
// Route protection is handled by individual pages checking auth state,
// not by blocking at the middleware level.
export default clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
};
