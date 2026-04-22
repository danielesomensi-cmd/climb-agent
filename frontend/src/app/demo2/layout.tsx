import { Archivo_Narrow, JetBrains_Mono, Inter } from "next/font/google";

const display = Archivo_Narrow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-demo2-display",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-demo2-mono",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-demo2-body",
  display: "swap",
});

export default function Demo2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <style>{`body{background:#0A0A0A !important;}`}</style>
      <div
        className={`${display.variable} ${mono.variable} ${body.variable}`}
        style={{ background: "#0A0A0A", color: "#F5F1EA", minHeight: "100vh" }}
      >
        {children}
      </div>
    </>
  );
}
