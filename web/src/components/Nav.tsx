"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRelay } from "@/lib/relay-context";

const LINKS = [
  { href: "/connect", label: "Connect" },
  { href: "/live", label: "Live Actions" },
  { href: "/tickers", label: "Active Tickers" },
  { href: "/settings", label: "Settings" },
  { href: "/lists", label: "Ticker Manager" },
  { href: "/history", label: "Trade History" },
  { href: "/calendar", label: "Calendar" },
];

export function Nav() {
  const pathname = usePathname();
  const { connectionState, disconnect } = useRelay();

  return (
    <nav style={navStyle}>
      <div style={brandStyle}>QuickStockBot</div>
      <div style={linksStyle}>
        {LINKS.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            style={{
              ...linkStyle,
              ...(pathname === href ? activeLinkStyle : {}),
            }}
          >
            {label}
          </Link>
        ))}
      </div>
      <div style={statusStyle}>
        <span
          style={{
            ...dotStyle,
            backgroundColor:
              connectionState === "connected"
                ? "#22c55e"
                : connectionState === "connecting"
                  ? "#f59e0b"
                  : connectionState === "error"
                    ? "#ef4444"
                    : "#6b7280",
          }}
        />
        <span style={{ color: "#9ca3af", fontSize: 12 }}>
          {connectionState === "connected"
            ? "Connected"
            : connectionState === "connecting"
              ? "Connecting…"
              : connectionState === "error"
                ? "Error"
                : "Disconnected"}
        </span>
        {connectionState === "connected" && (
          <button onClick={disconnect} style={disconnectBtnStyle}>
            Disconnect
          </button>
        )}
      </div>
    </nav>
  );
}

const navStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 24,
  padding: "12px 24px",
  backgroundColor: "#111827",
  borderBottom: "1px solid #1f2937",
  flexWrap: "wrap",
};

const brandStyle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 16,
  color: "#f9fafb",
  marginRight: 16,
  whiteSpace: "nowrap",
};

const linksStyle: React.CSSProperties = {
  display: "flex",
  gap: 4,
  flexWrap: "wrap",
  flex: 1,
};

const linkStyle: React.CSSProperties = {
  padding: "6px 12px",
  borderRadius: 6,
  fontSize: 13,
  color: "#9ca3af",
  textDecoration: "none",
  transition: "background 0.15s, color 0.15s",
};

const activeLinkStyle: React.CSSProperties = {
  backgroundColor: "#1f2937",
  color: "#f9fafb",
};

const statusStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginLeft: "auto",
};

const dotStyle: React.CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
  display: "inline-block",
};

const disconnectBtnStyle: React.CSSProperties = {
  fontSize: 12,
  padding: "4px 8px",
  borderRadius: 4,
  border: "1px solid #374151",
  backgroundColor: "transparent",
  color: "#9ca3af",
  cursor: "pointer",
};
