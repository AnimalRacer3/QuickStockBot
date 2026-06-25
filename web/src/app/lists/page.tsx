"use client";

import { useEffect, useState } from "react";
import { useRelay } from "@/lib/relay-context";

export default function ListsPage() {
  const { client, connectionState } = useRelay();
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [blacklist, setBlacklist] = useState<string[]>([]);
  const [wInput, setWInput] = useState("");
  const [bInput, setBInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  useEffect(() => {
    if (connectionState !== "connected" || !client) return;
    client.getLists().then(({ watchlist: w, blacklist: b }) => {
      setWatchlist(w);
      setBlacklist(b);
    });
  }, [client, connectionState]);

  async function save(w: string[], b: string[]) {
    if (!client) return;
    setSaving(true);
    try {
      const updated = await client.updateLists(w, b);
      setWatchlist(updated.watchlist);
      setBlacklist(updated.blacklist);
      setSavedMsg("Saved.");
      setTimeout(() => setSavedMsg(""), 2000);
    } finally {
      setSaving(false);
    }
  }

  function addToList(list: "watch" | "black") {
    const input = list === "watch" ? wInput.trim().toUpperCase() : bInput.trim().toUpperCase();
    if (!input) return;
    const newW = list === "watch" ? [...watchlist, input] : watchlist;
    const newB = list === "black" ? [...blacklist, input] : blacklist;
    if (list === "watch") setWInput("");
    else setBInput("");
    save(newW, newB);
  }

  function removeFromList(list: "watch" | "black", symbol: string) {
    const newW = list === "watch" ? watchlist.filter((s) => s !== symbol) : watchlist;
    const newB = list === "black" ? blacklist.filter((s) => s !== symbol) : blacklist;
    save(newW, newB);
  }

  if (connectionState !== "connected") {
    return (
      <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 80 }}>
        Not connected. <a href="/connect" style={{ color: "#3b82f6" }}>Connect first</a>.
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Ticker Manager</h1>
        {savedMsg && <span style={{ color: "#34d399", fontSize: 13 }}>{savedMsg}</span>}
        {saving && <span style={{ color: "#9ca3af", fontSize: 13 }}>Saving…</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <SymbolList
          title="Watchlist"
          symbols={watchlist}
          input={wInput}
          onInput={setWInput}
          onAdd={() => addToList("watch")}
          onRemove={(s) => removeFromList("watch", s)}
          color="#34d399"
        />
        <SymbolList
          title="Blacklist"
          symbols={blacklist}
          input={bInput}
          onInput={setBInput}
          onAdd={() => addToList("black")}
          onRemove={(s) => removeFromList("black", s)}
          color="#f87171"
        />
      </div>
    </div>
  );
}

function SymbolList({
  title, symbols, input, onInput, onAdd, onRemove, color
}: {
  title: string;
  symbols: string[];
  input: string;
  onInput: (v: string) => void;
  onAdd: () => void;
  onRemove: (s: string) => void;
  color: string;
}) {
  return (
    <div>
      <h2 style={{ fontSize: 13, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
        {title}
      </h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => onInput(e.target.value)}
          placeholder="AAPL"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onAdd(); } }}
          style={{
            flex: 1,
            padding: "8px 10px",
            borderRadius: 6,
            border: "1px solid #374151",
            backgroundColor: "#1f2937",
            color: "#f9fafb",
            fontSize: 13,
          }}
        />
        <button
          type="button"
          onClick={onAdd}
          style={{
            padding: "8px 14px",
            borderRadius: 6,
            border: "none",
            backgroundColor: color,
            color: "#111827",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          Add
        </button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {symbols.map((s) => (
          <div
            key={s}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "6px 10px",
              borderRadius: 6,
              backgroundColor: "#111827",
              border: "1px solid #1f2937",
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 600, color }}>{s}</span>
            <button
              type="button"
              onClick={() => onRemove(s)}
              style={{
                background: "none",
                border: "none",
                color: "#4b5563",
                cursor: "pointer",
                fontSize: 16,
                lineHeight: 1,
                padding: "0 4px",
              }}
            >
              ×
            </button>
          </div>
        ))}
        {symbols.length === 0 && (
          <div style={{ color: "#374151", fontSize: 12, textAlign: "center", padding: 12 }}>Empty</div>
        )}
      </div>
    </div>
  );
}
