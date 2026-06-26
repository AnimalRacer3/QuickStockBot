"use client";

import Link from "next/link";
import { useRelay } from "@/lib/relay-context";

export function BotConnectionCard() {
  const { connectionState } = useRelay();
  const isConnected = connectionState === "connected";

  return (
    <div className="rounded-xl border border-border bg-surface p-6 mb-6">
      <h2 className="font-semibold text-ink mb-1">Connect your bot</h2>
      <p className="text-sm text-ink-muted mb-4">
        After running the bot&apos;s setup wizard, enter the{" "}
        <strong className="text-ink">Relay URL</strong> and{" "}
        <strong className="text-ink">Connection Password</strong> from the wizard summary to link
        this dashboard to your running bot.
      </p>
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          href="/connect"
          className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold transition-opacity"
          style={{ background: "#10d98a", color: "#07090f" }}
        >
          Connect bot
        </Link>
        {isConnected && (
          <Link href="/live" className="text-sm text-accent hover:underline">
            Open live dashboard →
          </Link>
        )}
      </div>
    </div>
  );
}
