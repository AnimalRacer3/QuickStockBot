"use client";

import { useState } from "react";

export function ResendLicenseButton({ userId }: { userId: string }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleResend() {
    setState("loading");
    setErrorMsg("");
    try {
      const res = await fetch("/api/licenses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId }),
      });
      if (res.ok) {
        setState("done");
      } else {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        setErrorMsg(data.error ?? "Failed to issue license");
        setState("error");
      }
    } catch {
      setErrorMsg("Network error — please try again");
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <p className="text-sm text-ink-muted">
        License issued and emailed. Refresh this page to see your key.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-ink-muted">
        No license key found yet. Click below to issue one and send it to your email.
      </p>
      <button
        onClick={handleResend}
        disabled={state === "loading"}
        className="self-start text-sm font-semibold text-accent hover:underline disabled:opacity-50"
      >
        {state === "loading" ? "Sending…" : "Resend / issue license"}
      </button>
      {state === "error" && <p className="text-xs text-red-400">{errorMsg}</p>}
    </div>
  );
}
