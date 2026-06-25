import { RelayServer } from "./server.js";
import { logger } from "./logger.js";

const PORT = parseInt(process.env.RELAY_PORT ?? "8080", 10);
// In production (Railway), bind to 0.0.0.0 so the ingress can route traffic.
// Set RELAY_HOST=127.0.0.1 in dev to restrict to localhost only.
const HOST = process.env.RELAY_HOST ?? "0.0.0.0";
const VALIDATE_URL = process.env.SAAS_VALIDATE_URL ?? "http://localhost:3000/api/validate";
const CONNECTION_SECRET = process.env.RELAY_CONNECTION_SECRET ?? "";

const relay = new RelayServer({
  port: PORT,
  host: HOST,
  validateUrl: VALIDATE_URL,
  connectionSecret: CONNECTION_SECRET,
});

relay.listen().catch((err: unknown) => {
  logger.error("Failed to start relay", {
    err: err instanceof Error ? err.message : String(err),
  });
  process.exit(1);
});

process.on("SIGTERM", () => {
  relay
    .close()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
});

process.on("SIGINT", () => {
  relay
    .close()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
});
