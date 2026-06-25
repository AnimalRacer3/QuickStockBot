"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { RelayClient, type ConnectionState, type LogEvent, type StateUpdate } from "./relay-client";
import type { ExtendedTickerState } from "./types";

export interface RelayContextValue {
  client: RelayClient | null;
  connectionState: ConnectionState;
  connect: (url: string, password: string) => Promise<void>;
  disconnect: () => void;
  tickers: ExtendedTickerState[];
  logs: LogEvent[];
}

export const RelayContext = createContext<RelayContextValue>({
  client: null,
  connectionState: "disconnected",
  connect: async () => {},
  disconnect: () => {},
  tickers: [],
  logs: [],
});

const STORAGE_KEY = "qsb_relay_conn";

function saveConn(url: string, pw: string) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ url, pw }));
  } catch {}
}
function clearConn() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}
function loadConn(): { url: string; pw: string } | null {
  try {
    const s = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    return s ? (JSON.parse(s) as { url: string; pw: string }) : null;
  } catch {
    return null;
  }
}

export function RelayProvider({ children }: { children: React.ReactNode }) {
  const [client, setClient] = useState<RelayClient | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [tickers, setTickers] = useState<ExtendedTickerState[]>([]);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const clientRef = useRef<RelayClient | null>(null);

  const connect = useCallback(async (url: string, password: string) => {
    clientRef.current?.disconnect();

    const newClient = new RelayClient();
    clientRef.current = newClient;

    newClient.onConnectionStateChange(setConnectionState);
    newClient.onLog((event: LogEvent) => {
      setLogs((prev) => [event, ...prev].slice(0, 500));
    });
    newClient.onStateUpdate((payload: StateUpdate) => {
      if (payload.tickers) setTickers(payload.tickers);
    });

    await newClient.connect(url, password);
    saveConn(url, password);
    setClient(newClient);

    newClient.subscribeLogs().catch(() => {});
    newClient
      .getState()
      .then((state) => {
        if (state.tickers) setTickers(state.tickers);
      })
      .catch(() => {});
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    clientRef.current = null;
    clearConn();
    setClient(null);
    setTickers([]);
    setLogs([]);
  }, []);

  // Auto-reconnect from localStorage on mount
  const connectRef = useRef(connect);
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    const saved = loadConn();
    if (saved) {
      connectRef.current(saved.url, saved.pw).catch(() => clearConn());
    }
  }, []);

  useEffect(() => {
    return () => {
      clientRef.current?.disconnect();
    };
  }, []);

  return (
    <RelayContext.Provider
      value={{
        client,
        connectionState,
        connect,
        disconnect,
        tickers,
        logs,
      }}
    >
      {children}
    </RelayContext.Provider>
  );
}

export function useRelay() {
  return useContext(RelayContext);
}
