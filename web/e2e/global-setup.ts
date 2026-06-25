import { startMockRelay } from "./mock-relay";
import type { WebSocketServer } from "ws";

declare global {
  // eslint-disable-next-line no-var
  var __MOCK_RELAY_WSS__: WebSocketServer;
}

export default async function globalSetup() {
  global.__MOCK_RELAY_WSS__ = startMockRelay();
  console.log("[e2e] Mock relay started");
}
