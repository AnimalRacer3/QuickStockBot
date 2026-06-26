"use client";

import { useState } from "react";

interface Props {
  status: string | null;
  hasCustomer: boolean;
  prices: { basic: string | null; premium: string | null };
}

type Plan = "basic" | "premium";

export default function BillingActions({ status, hasCustomer, prices }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPlanPicker, setShowPlanPicker] = useState(false);

  async function startCheckout(trial: boolean, plan?: Plan) {
    setError("");
    setLoading(true);
    const res = await fetch("/api/billing/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trial, plan }),
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
            {loading ? "Loading…" : "Start 1-month free trial of Premium"}
          </button>

          {!showPlanPicker ? (
            <button
              onClick={() => setShowPlanPicker(true)}
              disabled={loading}
              style={styles.secondaryBtn}
            >
              Skip the trial — choose a plan
            </button>
          ) : (
            <div style={styles.planPicker}>
              <p style={styles.planLabel}>Choose your plan:</p>
              <div style={styles.planRow}>
                <button
                  onClick={() => startCheckout(false, "basic")}
                  disabled={loading}
                  style={styles.planBtn}
                >
                  <span style={{ ...styles.planName, color: "#0070f3" }}>Basic</span>
                  <span style={{ ...styles.planDesc, color: "#0070f3" }}>Core features</span>
                  {prices.basic && (
                    <span style={{ ...styles.planPrice, color: "#0070f3" }}>
                      {prices.basic}/month
                    </span>
                  )}
                </button>
                <button
                  onClick={() => startCheckout(false, "premium")}
                  disabled={loading}
                  style={{ ...styles.planBtn, ...styles.planBtnHighlight }}
                >
                  <span style={styles.planName}>Premium</span>
                  <span style={styles.planDesc}>All features</span>
                  {prices.premium && (
                    <span style={styles.planPrice}>{prices.premium}/month</span>
                  )}
                </button>
              </div>
              <button
                onClick={() => setShowPlanPicker(false)}
                style={styles.cancelLink}
                disabled={loading}
              >
                Cancel
              </button>
            </div>
          )}
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
  planPicker: {
    border: "1px solid #d0d0d0",
    borderRadius: 6,
    padding: "12px",
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  planLabel: { margin: 0, fontSize: 13, color: "#555", fontWeight: 600 },
  planRow: { display: "flex", gap: 8 },
  planBtn: {
    flex: 1,
    padding: "10px 12px",
    background: "#fff",
    border: "1px solid #0070f3",
    borderRadius: 4,
    cursor: "pointer",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center" as const,
    gap: 2,
  },
  planBtnHighlight: {
    background: "#0070f3",
    color: "#fff",
  },
  planName: { fontSize: 14, fontWeight: 600 },
  planDesc: { fontSize: 12, opacity: 0.75 },
  planPrice: { fontSize: 12, fontWeight: 600, marginTop: 4 },
  cancelLink: {
    background: "none",
    border: "none",
    color: "#888",
    cursor: "pointer",
    fontSize: 12,
    textDecoration: "underline",
    padding: 0,
    alignSelf: "flex-start" as const,
  },
  error: { color: "#e00", margin: 0, fontSize: 14 },
};
