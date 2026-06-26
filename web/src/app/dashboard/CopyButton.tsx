"use client";

import { useState } from "react";

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      className="text-xs text-ink-muted hover:text-ink transition-colors px-2 py-1 rounded border border-border hover:border-border-strong"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}
