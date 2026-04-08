# ESN WiFi Billing — API

Production-oriented FastAPI service for multi-router MikroTik hotspot billing: RBAC, customers, plans, vouchers, payments (mock + ClickPesa-ready), portal endpoints, analytics, Celery workers, and PostgreSQL via Alembic.

## Prerequisites

- Python 3.12+
- PostgreSQL 16+ (for local/API runtime and Alembic)
- Redis 7+ (for Celery and `/api/v1/health/ready`)
- (Optional) Docker Compose at repo root (`docker-compose.yml`)

## Configuration

Copy the monorepo `.env.example` to `.env` and adjust values. Important API keys:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@localhost:5432/esn_wifi` |
| `REDIS_URL` | Redis for Celery and readiness checks |
| `JWT_SECRET_KEY` | Strong secret for HS256 tokens |
| `ROUTER_CREDENTIALS_FERNET_KEY` | `Fernet` key for encrypted router passwords (required to create routers) |
| `MIKROTIK_USE_MOCK` | `true` in dev to use the mock RouterOS adapter (no real router) |
| `DEFAULT_PAYMENT_PROVIDER` | `mock` (local) or `clickpesa` |
| `CLICKPESA_*` | Optional live ClickPesa credentials + `CLICKPESA_CHECKSUM_KEY` for webhooks |
| `ROUTER_OFFLINE_AFTER_SECONDS` | NAS marked offline in background sweep if `last_seen_at` is older than this (default `900`) |
| `PORTAL_PUBLIC_SETTING_KEYS` | Comma-separated `system_settings` keys exposed on `GET /api/v1/portal/{slug}/settings` (default `company_name,support_email`) |
| `TRUSTED_HOSTS` | Optional comma-separated hosts for `TrustedHostMiddleware` (empty = off) |
| `PORTAL_RATE_LIMIT_BACKEND` | `redis` (default, multi-instance) or `memory` (single-process / tests) |
| `PORTAL_RATE_LIMIT_REDIS_FAIL_OPEN` | `true`: Redis errors → per-process memory limit + logs; `false` → HTTP **503** |
| `PORTAL_RATE_LIMIT_*` | Max requests per **window** + `*_WINDOW_SECONDS` (redeem / pay / status); see `app/core/rate_limit/` |
| `PENDING_PAYMENT_ABANDON_HOURS` | Celery reconciliation cancels stale `pending` payments after this age |
| `MIKROTIK_COMMAND_TIMEOUT_SECONDS` / `MIKROTIK_MAX_RETRIES` | Real NAS adapter resilience (mock adapter unchanged) |
| `MIKROTIK_USE_ROUTEROS_REST_STUB` | Use `RouterOSRestAdapterStub` instead of binary API stub |

Generate a Fernet key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Mock adapters and payment providers

- **MikroTik**: With `MIKROTIK_USE_MOCK=true`, `get_mikrotik_adapter` returns a fake RouterOS client (safe session ingest, sync, snapshots in dev/tests).
- **Payments**: `DEFAULT_PAYMENT_PROVIDER=mock` uses the in-process mock provider; no external PSP calls. ClickPesa wiring is optional behind env flags.

Tests override HTTP dependencies (DB session, health checks, current user) so **pytest does not require Postgres, Redis, routers, or real payments** for the default suite.

## Install

```bash
cd services/api
pip install -e ".[dev]"
```

## Migrations

Uses Alembic revisions (initial schema + incremental changes). Export `DATABASE_URL` for `env.py` → sync URL conversion.

```bash
export DATABASE_URL=postgresql+asyncpg://esn:esn@localhost:5432/esn_wifi
cd services/api
alembic upgrade head
```

## Seed (bootstrap / optional demo)

Requires DB migrated.

| `SEED_DEMO_DATA` | Effect |
|------------------|--------|
| `false` or unset | Permissions, roles, `admin@esn.local` + `support@esn.local`, site `hq`, portal branding shell, default portal settings — **no** sample plans, customers, vouchers, or payments. |
| `true` | Above **plus** demo plans, customers, voucher batch, mock payments, sample sessions, and a `demo-router` row if `ROUTER_CREDENTIALS_FERNET_KEY` is set. |

Router row is created only when the Fernet key is set (passwords must be encryptable).

**From `services/api`:**

```bash
export PYTHONPATH=$PWD
export DATABASE_URL=postgresql+asyncpg://esn:esn@localhost:5432/esn_wifi
python3 -m app.seed
```

**From repository root:**

```bash
python3 scripts/seed_demo.py
```

Seeds (idempotent): permissions, **admin** + **support** roles, admin + support users, site `hq`, portal branding, plans linked to the demo router when present, customers (`customer@example.com`, `active@demo.esn`, `expired@demo.esn`), voucher batch, demo codes (`SEED-REDEEM-OK`, `SEED-REDEEM-USED`, `SEED-REDEEM-EXP`), successful + pending mock payments, access grants (including payment-linked `SEED-ORDER-1`), notifications, hotspot session when a router exists, `company_name` + `support_email` settings.

- Admin: `admin@esn.local` / `ChangeMe123!` (override `SEED_ADMIN_PASSWORD`)
- Support: `support@esn.local` / `Support123!` (override `SEED_SUPPORT_PASSWORD`)

## Run API

```bash
export PYTHONPATH=$PWD
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

OpenAPI: http://localhost:8000/docs

### Health and readiness

- `GET /api/v1/health/live` — process is up.
- `GET /api/v1/health/ready` — checks **database** (`SELECT 1`) and **Redis** `PING`. Returns `503` with `{ ready, checks }` when a dependency fails (errors are logged). Tests inject successful checks via FastAPI dependency overrides (`check_database_connectivity`, `check_redis_connectivity`).

## Celery

```bash
cd services/api
export PYTHONPATH=$PWD
celery -A app.workers.celery_app worker -l info
celery -A app.workers.celery_app beat -l info
```

Beat schedules (UTC):

- Router resource sync (`esn.routers.sync_all`) — every 5 minutes  
- Hotspot session ingest (`esn.routers.ingest_hotspot_sessions`) — every 3 minutes  
- Stale router offline sweep (`esn.routers.mark_offline_stale`) — every 2 minutes  
- Reconciliation (`esn.reconciliation.run_once`) — access-grant expiry + stale pending payments — every 15 minutes  
- Session / voucher maintenance tasks — full schedule in `app/workers/celery_app.py`

## Docker (monorepo)

From repository root:

```bash
docker compose up -d postgres redis api worker beat
```

Apply migrations and seed inside the stack:

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
```

## Tests

```bash
cd services/api
pytest
```

The default suite runs **without** Postgres/Redis/MikroTik by using dependency overrides and pure unit tests. Expect **0 skipped** tests in normal runs.

## Core business flows

### Voucher redemption

- **Service**: `app/modules/vouchers/redemption.py` — `redeem_voucher` loads the code with `SELECT … FOR UPDATE`, validates PIN, expiry, active plan, and (portal) whether the plan is offered at the site (aligned with portal plan listing).
- **Access**: Creates a `CustomerAccessGrant` with optional `site_id`, marks the voucher `used`, audit `voucher.redeemed`, customer notification `voucher_redeemed`.
- **Idempotency**: Same customer repeating redemption gets the same payload; another customer receives **409 Conflict**. Grant insert races use a savepoint + unique index on `voucher_id`.
- **HTTP**: `POST /api/v1/portal/{slug}/redeem` (requires `customer_id`), `POST /api/v1/vouchers/redeem` (admin; optional `site_id` enforces plan/site rules).

### Payment → access activation

- **Canonical**: `activate_access_after_successful_payment` in `app/modules/payments/service.py` (`apply_payment_success` is an alias).
- **First success**: one `success` payment event, one entitlement grant when `customer_id` + `plan_id` exist (unique per `payment_id`), voucher-batch unlock if applicable, one customer notification. **Replays** only repair missing grants and re-sync batch flags — no duplicate events or notifications.
- **Failures**: `apply_payment_failed` no-ops if status is already **failed** or **success** (no downgrade).

### Customer access

- **Model**: `customer_access_grants` + optional `site_id`; entitlement derived by `compute_grant_entitlement`.
- **HTTP**: `GET /api/v1/customers/{id}` (includes detailed grants), `GET /api/v1/customers/{id}/access-grants`, `GET /api/v1/portal/{slug}/access-status?customer_id=…`.

### Router operations

- **Service**: `app/modules/routers/router_operations.py` — sync, disconnect, block/unblock, ingest, live sessions, whitelist. Responses include a normalized **`nas`** object (`ok` or error `code` / `retryable`). Real adapters are wrapped with `ResilientMikroTikAdapter` (timeout + retries); the mock adapter is not wrapped.

### Migrations `003` / `004`

- **003**: `site_id` on grants and partial unique indexes (`payment_id`, `voucher_id`) for idempotent entitlements.  
- **004**: `payment_callbacks.dedupe_key` + unique `(provider, dedupe_key)` for PSP webhook replay protection.

Run **`alembic upgrade head`** before any production rollout (see `docs/BACKEND_ROLLOUT.md`).

## ClickPesa

Webhook route: `POST /api/v1/payments/webhooks/clickpesa`  

Payload verification follows ClickPesa’s canonical JSON + HMAC-SHA256 checksum rules (`app/integrations/payments/checksum.py`). Configure `CLICKPESA_CHECKSUM_KEY` and enable `CLICKPESA_ENABLED` when the live charge API is wired in `ClickPesaProvider.initiate_payment`.

`verify_webhook` returns a normalized `WebhookVerificationResult`; `callback_pipeline.process_payment_webhook` stores callbacks with a **`dedupe_key`** so gateway replays do not double-activate (audit: `payment.webhook_duplicate_skipped` / `payment.webhook_processed`).

## API highlights

- **Routers**: CRUD, sync, ingest, block/whitelist, `GET /routers/{id}/status`, `GET /routers/{id}/snapshots`, sync logs.
- **Portal (public)**: branding, settings, status, plans, pay, **redeem** (standard access payload), **access-status**, session-status.
- **Sites**: CRUD-style + soft delete, `PUT /sites/{id}/portal-branding`.
- **RBAC**: roles CRUD, permission assignment, `GET /permissions`, user role assign/remove.
- **Audit**: `GET /api/v1/audit-logs` with filters and pagination.
- **Analytics**: `GET /api/v1/analytics/overview`, `/revenue`, `/plans`, `/routers`, `/sessions` (+ legacy `/summary`, `/top-plans`).
- **Settings**: `GET/PUT /api/v1/settings` (admin).

## Layout

- `app/api/v1/routes/` — versioned HTTP routers  
- `app/modules/*` — domain models per feature  
- `app/integrations/mikrotik/` — RouterOS port + mock/real adapters  
- `app/integrations/payments/` — Provider interface + mock + ClickPesa skeleton  
- `app/workers/` — Celery app & tasks  
- `alembic/` — migrations  
- `tests/` — pytest suite  
