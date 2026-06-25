# QuickStockBot — Operator Runbook

This runbook covers deploying and operating the QuickStockBot SaaS platform.

---

## Architecture overview

```
Internet → Railway ingress (TLS) → Next.js Web  (web service)
                                 → Node.js Relay (relay service)
                                 → PostgreSQL    (Railway Postgres plugin)

Bot (on user machine) → Relay (outbound WSS)
Browser (user)        → Web  (HTTPS) + Relay (WSS)
```

TLS is terminated at Railway's ingress for all public endpoints. The relay and
web services communicate internally and with user devices over Railway-managed
TLS — no self-signed certificate management is required.

---

## Deploy — initial setup

### 1. Provision Railway services

Create a Railway project with three services:

| Service | Source | Template |
|---------|--------|----------|
| `web` | `/web` directory | Nixpacks |
| `relay` | `/relay` directory | Nixpacks |
| `postgres` | — | Railway Postgres plugin |

Railway auto-detects `railway.toml` in each service directory for build and
start commands.

### 2. Link the Postgres plugin

In the `web` service settings, add a reference variable:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

### 3. Set required environment variables

#### web service

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Injected by Postgres plugin | — |
| `SESSION_SECRET` | JWT signing key, 32+ random chars | `openssl rand -hex 32` |
| `ADMIN_API_KEY` | Protects the license revoke endpoint | `openssl rand -hex 24` |
| `LICENSE_DB_PATH` | SQLite license DB path | `/data/licenses.db` |
| `STRIPE_SECRET_KEY` | Stripe live or test key | `sk_live_...` |
| `STRIPE_PRICE_ID` | Stripe recurring price ID | `price_...` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | `whsec_...` |
| `RESEND_API_KEY` | Resend transactional email | `re_...` |
| `RESEND_FROM` | Verified sender address | `noreply@yourdomain.com` |

#### relay service

| Variable | Description | Example |
|----------|-------------|---------|
| `RELAY_PORT` | Port to bind (Railway sets `PORT`) | Use `${{PORT}}` |
| `RELAY_HOST` | Bind address (must be `0.0.0.0` on Railway) | `0.0.0.0` |
| `RELAY_CONNECTION_SECRET` | HMAC key shared with bot | `openssl rand -hex 32` |
| `SAAS_VALIDATE_URL` | License validation endpoint | `https://app.example.com/api/licenses/validate` |

> **Security note:** `RELAY_CONNECTION_SECRET` must match `CONNECTION_PASSWORD`
> in each bot's `.env`. Rotate together (see _Rotate relay secret_ below).

### 4. Stripe webhook

In the Stripe dashboard, create a webhook pointing to:
```
https://<web-domain>/api/webhooks/stripe
```
Events: `checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`.

Copy the signing secret to `STRIPE_WEBHOOK_SECRET`.

### 5. Verify CI gate

Branch protection on `main` must require the `Deploy gate` CI job to pass
before Railway triggers a deploy. Configure this under
_GitHub → Settings → Branches → main → Require status checks:_
add `Deploy gate`.

---

## Deploy — routine updates

```bash
git checkout main
git pull origin main
# Railway auto-deploys when main changes and CI is green
```

Railway waits for the `deploy-gate` GitHub Actions job to succeed before
deploying. If any job fails, the deploy is blocked.

---

## Rotate secrets

### Rotate SESSION_SECRET

1. Generate: `openssl rand -hex 32`
2. Update `SESSION_SECRET` in Railway web service environment variables.
3. All active sessions are invalidated immediately — users must log in again.
4. Redeploy the web service.

### Rotate relay HMAC secret

> Affects ALL connected bots. Coordinate with users before rotating.

1. Generate: `openssl rand -hex 32`
2. Update `RELAY_CONNECTION_SECRET` in Railway relay service.
3. Ask all users to update `CONNECTION_PASSWORD` in their bot's `.env` and
   restart the bot. The installer wizard has a "Rotate password" step.
4. Bots with the old secret will be rejected at registration with `AUTH_FAILED`.

### Rotate ADMIN_API_KEY

1. Generate: `openssl rand -hex 24`
2. Update `ADMIN_API_KEY` in Railway web service.
3. Update any automation scripts that call the revoke endpoint.

### Rotate Stripe webhook secret

1. In Stripe dashboard: Webhooks → Edit → Roll signing secret.
2. Update `STRIPE_WEBHOOK_SECRET` in Railway web service.
3. Redeploy.

---

## Revoke a license

```bash
curl -X POST https://<web-domain>/api/licenses/<LICENSE_KEY>/revoke \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

The relay will reject the bot on its next registration attempt. Active sessions
continue until the bot disconnects and reconnects.

To force immediate disconnection, restart the relay service in Railway — all
bots will re-register and the revoked key will be rejected.

---

## Issue a license manually

```bash
curl -X POST https://<web-domain>/api/licenses \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"userId": "<UUID>"}'
```

---

## Monitor

- **Railway logs**: view real-time logs for each service in the Railway dashboard.
- **Relay**: logs are structured JSON. Key fields: `bot_id`, `account_id`,
  `level`, `msg`.
- **Web**: Next.js logs to stdout; filter for `[error]` prefix.
- **Alerts**: set up Railway metrics alerts on CPU/memory for relay; add a Stripe
  webhook for `payment_intent.payment_failed` to catch billing issues.

---

## Scale relay

The relay uses in-memory routing maps. For multiple relay instances, add Redis:

1. Provision a Railway Redis plugin.
2. Set `REDIS_URL=${{Redis.REDIS_URL}}` in the relay service.
3. The relay will use Redis for bot registration and subscription maps.
   (Redis adapter implementation required — see `relay/src/routing.ts`.)

---

## Database

### Run migrations

```bash
# In the web service Railway shell:
npx prisma migrate deploy
```

### Backup Postgres

Use Railway's built-in backup scheduler or `pg_dump`:
```bash
pg_dump "$DATABASE_URL" | gzip > backup-$(date +%Y%m%d).sql.gz
```

### License SQLite DB

The license database (`licenses.db`) is stored on the Railway volume mount.
Back up regularly:
```bash
sqlite3 /data/licenses.db ".dump" | gzip > licenses-$(date +%Y%m%d).sql.gz
```

---

## Security posture

| Control | Status | Notes |
|---------|--------|-------|
| Argon2id password hashing | ✅ | `web/src/lib/auth.ts` |
| HMAC-SHA256 bot auth | ✅ | `relay/src/auth.ts` |
| Rate limiting — login (10/min/IP) | ✅ | `web/src/lib/rate-limit.ts` |
| Rate limiting — signup (5/min/IP) | ✅ | `web/src/lib/rate-limit.ts` |
| Rate limiting — relay WS (20 msg/s) | ✅ | `relay/src/rate-limiter.ts` |
| TLS for web + relay | ✅ | Railway ingress; no app-level cert |
| JWT session cookies (httpOnly, Secure) | ✅ | `web/src/lib/session.ts` |
| Bot opens no inbound ports | ✅ | Bot is a pure outbound WS client |
| Relay bind address configurable | ✅ | `RELAY_HOST` env var |
| Secrets via env vars only | ✅ | Never logged or committed |
| Admin endpoint requires `X-Admin-Key` | ✅ | License revoke / issue |
| Input validation on all API routes | ✅ | Zod / manual checks |
| Account isolation on relay | ✅ | `account_id` scoping in routing map |
