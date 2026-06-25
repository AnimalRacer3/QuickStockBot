"use client";

import { useRelay } from "@/lib/relay-context";
import SettingsPageInner from "./page-inner";

export default function SettingsPage() {
  const { connectionState } = useRelay();

  if (connectionState !== "connected") {
    return (
      <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 80 }}>
        Not connected.{" "}
        <a href="/connect" style={{ color: "#3b82f6" }}>
          Connect first
        </a>
        .
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 24 }}>Settings</h1>
      <SettingsPageInner />
    </div>
  );
}
