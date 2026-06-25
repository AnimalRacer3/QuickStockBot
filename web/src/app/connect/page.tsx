"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRelay } from "@/lib/relay-context";

export default function ConnectPage() {
  const { connect, connectionState } = useRelay();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await connect(url.trim(), password);
      router.push("/live");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: "80px auto" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Connect to Bot</h1>
      <p style={{ color: "#9ca3af", marginBottom: 32, fontSize: 14 }}>
        Enter your relay URL and connection password to connect.
      </p>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <label style={labelStyle}>
          Relay URL
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="ws://localhost:8080"
            required
            aria-label="Relay URL"
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Connection Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            aria-label="Connection Password"
            style={inputStyle}
          />
        </label>
        {error && (
          <div role="alert" style={{ color: "#ef4444", fontSize: 13, padding: "8px 12px", backgroundColor: "#1f1414", borderRadius: 6, border: "1px solid #7f1d1d" }}>
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={connectionState === "connecting"}
          style={btnStyle}
        >
          {connectionState === "connecting" ? "Connecting…" : "Connect"}
        </button>
      </form>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  fontSize: 13,
  color: "#d1d5db",
};

const inputStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 8,
  border: "1px solid #374151",
  backgroundColor: "#1f2937",
  color: "#f9fafb",
  fontSize: 14,
  outline: "none",
};

const btnStyle: React.CSSProperties = {
  padding: "10px 20px",
  borderRadius: 8,
  border: "none",
  backgroundColor: "#3b82f6",
  color: "#fff",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  marginTop: 8,
};
