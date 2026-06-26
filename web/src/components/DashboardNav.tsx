"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRelay } from "@/lib/relay-context";
import { Menu, X, Activity, Wifi, Settings, LayoutList } from "lucide-react";

const LINKS = [
  { href: "/connect", label: "Connect" },
  { href: "/live", label: "Live Actions" },
  { href: "/tickers", label: "Active Tickers" },
  { href: "/settings", label: "Settings" },
  { href: "/lists", label: "Ticker Manager" },
  { href: "/history", label: "Trade History" },
  { href: "/calendar", label: "Calendar" },
];

const BOTTOM_NAV = [
  { href: "/live", label: "Live", icon: Activity, center: false },
  { href: "/connect", label: "Connect", icon: Wifi, center: true },
  { href: "/settings", label: "Settings", icon: Settings, center: false },
  { href: "/lists", label: "Tickers", icon: LayoutList, center: false },
];

function dotColor(state: string) {
  if (state === "connected") return "#22c55e";
  if (state === "connecting") return "#f59e0b";
  if (state === "error") return "#ef4444";
  return "#6b7280";
}

function statusLabel(state: string) {
  if (state === "connected") return "Connected";
  if (state === "connecting") return "Connecting…";
  if (state === "error") return "Error";
  return "Disconnected";
}

export function DashboardNav() {
  const pathname = usePathname();
  const { connectionState, disconnect } = useRelay();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const dot = dotColor(connectionState);

  return (
    <>
      {/* ── DESKTOP nav — hidden on mobile ── */}
      <nav className="hidden sm:flex items-center gap-6 px-6 py-3 bg-gray-900 border-b border-gray-800 flex-wrap">
        <div className="font-bold text-base text-gray-50 mr-4 whitespace-nowrap">QuickStockBot</div>
        <div className="flex gap-1 flex-wrap flex-1">
          {LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded text-sm no-underline transition-colors ${
                pathname === href ? "bg-gray-800 text-gray-50" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: dot }} />
          <span className="text-gray-400 text-xs">{statusLabel(connectionState)}</span>
          {connectionState === "connected" && (
            <button
              onClick={disconnect}
              className="text-xs px-2 py-1 rounded border border-gray-700 bg-transparent text-gray-400 cursor-pointer"
            >
              Disconnect
            </button>
          )}
        </div>
      </nav>

      {/* ── MOBILE top bar — hidden on sm+ ── */}
      <nav className="flex sm:hidden items-center px-4 py-3 bg-gray-900 border-b border-gray-800">
        <div className="font-bold text-base text-gray-50 flex-1">QuickStockBot</div>
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: dot }} />
          <button
            onClick={() => setDrawerOpen(true)}
            className="p-1.5 text-gray-400 rounded"
            aria-label="Open menu"
          >
            <Menu size={22} />
          </button>
        </div>
      </nav>

      {/* ── MOBILE drawer — hidden on sm+ ── */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex sm:hidden">
          {/* backdrop */}
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          {/* panel slides in from right */}
          <div className="relative ml-auto w-72 h-full bg-gray-900 flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
              <span className="font-bold text-gray-50 text-sm">Menu</span>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-1.5 text-gray-400"
                aria-label="Close menu"
              >
                <X size={22} />
              </button>
            </div>
            <div className="flex flex-col gap-1 p-3 flex-1 overflow-y-auto">
              {LINKS.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setDrawerOpen(false)}
                  className={`px-3 py-2.5 rounded text-sm no-underline ${
                    pathname === href ? "bg-gray-800 text-gray-50" : "text-gray-400"
                  }`}
                >
                  {label}
                </Link>
              ))}
            </div>
            {connectionState === "connected" && (
              <div className="p-4 border-t border-gray-800">
                <button
                  onClick={() => {
                    disconnect();
                    setDrawerOpen(false);
                  }}
                  className="w-full text-sm px-3 py-2 rounded border border-gray-700 bg-transparent text-gray-400 cursor-pointer"
                >
                  Disconnect
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── MOBILE bottom nav bar — hidden on sm+ ── */}
      <nav className="fixed bottom-0 inset-x-0 z-40 flex sm:hidden items-end bg-gray-900 border-t border-gray-800 h-16">
        {BOTTOM_NAV.map(({ href, label, icon: Icon, center }) => {
          const active = pathname === href;
          if (center) {
            return (
              <Link
                key={href}
                href={href}
                className="flex-1 flex flex-col items-center justify-end pb-2"
              >
                <div
                  className={`flex flex-col items-center justify-center w-14 h-14 rounded-full -mt-5 mb-1 shadow-lg border border-gray-700 ${
                    active ? "bg-blue-600 border-blue-500" : "bg-gray-800"
                  }`}
                >
                  <Icon size={24} className={active ? "text-white" : "text-gray-400"} />
                </div>
                <span
                  className={`text-[10px] leading-none ${
                    active ? "text-blue-400" : "text-gray-500"
                  }`}
                >
                  {label}
                </span>
              </Link>
            );
          }
          return (
            <Link
              key={href}
              href={href}
              className="flex-1 flex flex-col items-center justify-center gap-1 pb-1"
            >
              <Icon size={20} className={active ? "text-blue-400" : "text-gray-500"} />
              <span
                className={`text-[10px] leading-none ${active ? "text-blue-400" : "text-gray-500"}`}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
