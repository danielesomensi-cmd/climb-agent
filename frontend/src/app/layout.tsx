import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Toaster } from "sonner";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
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
    url: "https://climb-agent.vercel.app",
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
  themeColor: "#1a1a2e",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
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
          </Providers>
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
