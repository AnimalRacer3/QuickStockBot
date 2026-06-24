import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "QuickStockBot",
  description: "Stock trading bot dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
