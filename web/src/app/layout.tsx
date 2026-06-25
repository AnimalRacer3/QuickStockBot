import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ClientLayout } from "@/components/ClientLayout";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "QuickStockBot — Automated Stock Trading Bot",
  description:
    "Paper trade first, go live when you're confident. QuickStockBot watches the tape, reads the news, and executes your strategy around the clock.",
  openGraph: {
    title: "QuickStockBot — Automated Stock Trading Bot",
    description:
      "AI-powered trading bot with paper-to-live mode, multi-source news analysis, and real-time dashboards.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans min-h-screen flex flex-col bg-bg text-ink">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
