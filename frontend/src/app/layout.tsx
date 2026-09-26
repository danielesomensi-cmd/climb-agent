import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/next";
import { Toaster } from "sonner";
import { Providers } from "./providers";
import { SwUpdateBanner } from "@/components/sw-update-banner";
import { AttributionCapture } from "@/components/attribution-capture";
import { InstallCapture } from "@/components/install-capture";
import { SessionScopeGuard } from "@/components/session-scope-guard";
import "./globals.css";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://climbagent.app";

export const metadata: Metadata = {
  metadataBase: new URL(APP_URL),
  title: "climb-agent",
  description:
    "AI-powered climbing training planner. 80+ research papers, one personalized plan.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "climb-agent",
  },
  icons: {
    apple: "/icons/icon-192.png",
  },
  openGraph: {
    title: "climb-agent",
    description:
      "AI-powered climbing training planner. 80+ research papers, one personalized plan.",
    url: APP_URL,
    siteName: "climb-agent",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "climb-agent",
    description: "AI-powered climbing training planner.",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f121a",
  width: "device-width",
  initialScale: 1,
  // No maximumScale: pinch-zoom must stay available (WCAG 1.4.4) — in falesia
  // al sole le label piccole sono illeggibili senza zoom.
  viewportFit: "cover",
};

/*
 * A286 — Clerk non era tematizzato: card bianca con testo nero in un'app
 * dark-only, ed è la schermata che chiude il wizard di onboarding. Si usa
 * `variables` invece di @clerk/themes per non aggiungere una dipendenza; i
 * valori sono gli stessi token A214 di globals.css, scritti per esteso perché
 * Clerk deriva le sue scale dal colore e non risolve var() in modo affidabile.
 */
const clerkAppearance = {
  variables: {
    colorPrimary: "hsl(340, 85%, 58%)",
    colorTextOnPrimaryBackground: "hsl(340, 65%, 10%)",
    colorBackground: "hsl(222, 24%, 13%)",
    colorText: "hsl(210, 20%, 98%)",
    colorTextSecondary: "hsl(215, 14%, 62%)",
    colorInputBackground: "hsl(222, 20%, 19%)",
    colorInputText: "hsl(210, 20%, 98%)",
    colorNeutral: "hsl(210, 20%, 98%)",
    colorDanger: "hsl(0, 75%, 58%)",
    colorSuccess: "hsl(145, 65%, 48%)",
    colorWarning: "hsl(40, 90%, 55%)",
    borderRadius: "10px",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider appearance={clerkAppearance}>
      <html lang="en" className="dark" suppressHydrationWarning>
        <body className={`${inter.variable} font-sans antialiased`}>
          <Providers>
            <div className="mx-auto min-h-screen max-w-3xl">{children}</div>
            {/* A286 — nella PWA installata i toast finivano sotto il notch:
                l'offset di default di sonner è 32px dal bordo dello schermo,
                che su iPhone è dentro la status bar. */}
            <Toaster
              richColors
              position="top-center"
              offset="calc(env(safe-area-inset-top) + 16px)"
              mobileOffset="calc(env(safe-area-inset-top) + 12px)"
            />
            <SwUpdateBanner />
            <AttributionCapture />
            <InstallCapture />
            <SessionScopeGuard />
          </Providers>
          <Analytics />
          <script
            dangerouslySetInnerHTML={{
              __html: `if("serviceWorker"in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js"))`,
            }}
          />
        </body>
      </html>
    </ClerkProvider>
  );
}
