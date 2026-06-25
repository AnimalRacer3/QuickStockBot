import type { Metadata } from "next";
import { RelayProvider } from "@/lib/relay-context";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "QuickStockBot",
  description: "Stock trading bot dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, backgroundColor: "#0f172a", color: "#f9fafb", fontFamily: "system-ui, sans-serif", minHeight: "100vh" }}>
        <RelayProvider>
          <Nav />
          <main style={{ padding: "24px" }}>{children}</main>
        </RelayProvider>
      </body>
    </html>
  );
}
