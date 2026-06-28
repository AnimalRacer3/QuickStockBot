import { RelayServer } from "./server.js";
import { logger } from "./logger.js";

const PORT = parseInt(process.env.PORT ?? process.env.RELAY_PORT ?? "8080", 10);
// In production (Railway), bind to 0.0.0.0 so the ingress can route traffic.
// Set RELAY_HOST=127.0.0.1 in dev to restrict to localhost only.
const HOST = process.env.RELAY_HOST ?? "0.0.0.0";
const VALIDATE_URL = process.env.SAAS_VALIDATE_URL ?? "http://localhost:3000/api/licenses/validate";
const CONNECTION_SECRET = process.env.RELAY_CONNECTION_SECRET ?? "";
const SAAS_SECRET = process.env.SAAS_SECRET ?? "";

if (VALIDATE_URL.includes("localhost") || VALIDATE_URL.includes("127.0.0.1")) {
  logger.warn(
    "SAAS_VALIDATE_URL points to localhost — bot authentication will fail in production. " +
      "Set SAAS_VALIDATE_URL to your web app's /api/licenses/validate endpoint."
  );
}

const relay = new RelayServer({
  port: PORT,
  host: HOST,
  validateUrl: VALIDATE_URL,
  connectionSecret: CONNECTION_SECRET,
  saasSecret: SAAS_SECRET,
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
