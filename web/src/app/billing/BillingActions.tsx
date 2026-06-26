"use client";

import { useState } from "react";

interface Props {
  status: string | null;
  hasCustomer: boolean;
}

export default function BillingActions({ status, hasCustomer }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startCheckout(trial: boolean) {
    setError("");
    setLoading(true);
    const res = await fetch("/api/billing/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trial }),
    });
    setLoading(false);
    if (res.ok) {
      const data = (await res.json()) as { url?: string };
      if (data.url) window.location.href = data.url;
    } else {
      const data = (await res.json().catch(() => ({}))) as { error?: string };
      setError(data.error ?? "Failed to start checkout");
    }
  }

  async function openPortal() {
    setError("");
    setLoading(true);
    const res = await fetch("/api/billing/portal", { method: "POST" });
    setLoading(false);
    if (res.ok) {
      const data = (await res.json()) as { url?: string };
      if (data.url) window.location.href = data.url;
    } else {
      const data = (await res.json().catch(() => ({}))) as { error?: string };
      setError(data.error ?? "Failed to open portal");
    }
  }

  const needsCheckout = !status || status === "canceled";
  const needsPortal =
    hasCustomer && (status === "trialing" || status === "active" || status === "past_due");

  return (
    <div style={styles.actions}>
      {error && <p style={styles.error}>{error}</p>}
      {needsCheckout && (
        <>
          <button onClick={() => startCheckout(true)} disabled={loading} style={styles.primaryBtn}>
            {loading ? "Loading…" : "Start 1-month free trial"}
          </button>
          <button
            onClick={() => startCheckout(false)}
            disabled={loading}
            style={styles.secondaryBtn}
          >
            {loading ? "Loading…" : "Subscribe now — skip the trial"}
          </button>
        </>
      )}
      {needsPortal && (
        <button onClick={openPortal} disabled={loading} style={styles.secondaryBtn}>
          {loading ? "Loading…" : "Manage subscription"}
        </button>
      )}
    </div>
  );
}

const styles = {
  actions: { display: "flex", flexDirection: "column" as const, gap: 12, marginTop: 8 },
  primaryBtn: {
    padding: "10px 16px",
    background: "#0070f3",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
  secondaryBtn: {
    padding: "10px 16px",
    background: "#fff",
    color: "#0070f3",
    border: "1px solid #0070f3",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: 14,
  },
  error: { color: "#e00", margin: 0, fontSize: 14 },
};
