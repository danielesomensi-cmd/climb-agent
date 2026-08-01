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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark" suppressHydrationWarning>
        <body className={`${inter.variable} font-sans antialiased`}>
          <Providers>
            <div className="mx-auto min-h-screen max-w-3xl">{children}</div>
            <Toaster richColors position="top-center" />
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
