# Backend rollout — production hardening

## Pre-flight checklist

1. **Alembic at head** — run `alembic upgrade head` on the production database before enabling traffic. Revision `004_payment_callback_dedupe` adds webhook replay protection (`payment_callbacks.dedupe_key` + unique `(provider, dedupe_key)`).
2. **Secrets** — set `JWT_SECRET_KEY`, `ROUTER_CREDENTIALS_FERNET_KEY`, and ClickPesa secrets in a vault; never commit `.env`.
3. **Trusted hosts** — set `TRUSTED_HOSTS` to your API hostname(s) behind TLS; leave empty only for controlled dev.
4. **CORS** — restrict `CORS_ORIGINS` to known admin/portal origins.
5. **Celery** — run worker + beat; confirm schedules in `app/workers/celery_app.py` (includes `esn.reconciliation.run_once` every 15 minutes).
6. **Seed / demo** — `python -m app.seed` is for **non-production** demos only.

## Idempotency notes

- **Payments**: `apply_payment_success` / failed paths are safe on replay. **Webhooks**: duplicate gateway delivery is deduped on `(provider, dedupe_key)` (txn id + order ref + event/status when needed).
- **Voucher redeem**: portal requires `customer_id` (breaking vs anonymous flows); document for frontend.
- **Reconciliation tasks**: `reconcile_expired_access_grants` and `reconcile_stale_pending_payments` are safe to rerun.

## Payment provider layout

- **Protocol**: `app/integrations/payments/protocol.py` — `PaymentProvider` (`initiate_payment`, `verify_webhook` → `WebhookVerificationResult`).
- **Mapping vs activation**: adapters only verify + normalize; `callback_pipeline.process_payment_webhook` persists callbacks and calls `apply_payment_*`.
- **Implementations**: `mock_provider.py`, `clickpesa.py`; errors: `errors.py` + `normalize_provider_http_error` for HTTP initiate failures.

## MikroTik layout

- **Port**: `app/integrations/mikrotik/protocol.py` — `MikroTikHotspotPort`.
- **Mock**: `mock_adapter.py` (tests / `MIKROTIK_USE_MOCK=true`).
- **Real binary stub**: `adapter.py` + `client.py` (NotImplemented until wired).
- **REST stub contract**: `routeros_rest_stub.py` when `MIKROTIK_USE_ROUTEROS_REST_STUB=true`.
- **Resilience**: `resilience.ResilientMikroTikAdapter` wraps real transports (timeout + retries). **Orchestration** stays in `router_operations` only; responses include a normalized `nas` object (`ok` / error `code`, `message`, `retryable`).

## Public route safety

- Portal routes are **unauthenticated**; responses must not include internal secrets.
- **Rate limiting** (`app/core/rate_limit/`): default `PORTAL_RATE_LIMIT_BACKEND=redis` uses an atomic **sliding window** in Redis (Lua: ZSET + `ZREMRANGEBYSCORE`). Keys include `action`, normalized `site_slug`, normalized client IP, and safe fingerprints (`customer_id`, SHA-256 voucher code digest, phone digit digest for pay, MAC digest for session-status). **Protected routes**: `POST …/redeem`, `POST …/pay`, `GET …/access-status`, `POST …/session-status`.
- **Redis outage**: `PORTAL_RATE_LIMIT_REDIS_FAIL_OPEN=true` (default) logs a warning with stack trace, then enforces a **per-process memory** sliding window (weaker under multi-worker, but keeps UX up). Set `FAIL_OPEN=false` for **fail-closed** HTTP **503** (`service_unavailable`) when Redis cannot be reached — stricter for high-security deployments.
- For **local dev** without Redis, set `PORTAL_RATE_LIMIT_BACKEND=memory`.
- Webhook route accepts raw JSON; signature enforced when `CLICKPESA_CHECKSUM_KEY` is set.

## API changelog (condensed)

- **0.2.0**: OpenAPI tags and examples; portal rate limits (`429` on abuse); `GET /routers/{id}/sessions` now returns `{ sessions, nas, … }` (was a bare list). `POST /routers/{id}/sync` returns full structured payload including `nas`. Payment webhooks use dedupe keys. New env vars: `TRUSTED_HOSTS`, `PORTAL_RATE_LIMIT_*`, `PENDING_PAYMENT_ABANDON_HOURS`, `MIKROTIK_COMMAND_TIMEOUT_SECONDS`, `MIKROTIK_MAX_RETRIES`, `MIKROTIK_USE_ROUTEROS_REST_STUB`.
- **0.2.1**: Portal limits are **Redis-backed** by default (`PORTAL_RATE_LIMIT_BACKEND`, `PORTAL_RATE_LIMIT_*_WINDOW_SECONDS`, `PORTAL_RATE_LIMIT_REDIS_FAIL_OPEN`, `PORTAL_RATE_LIMIT_REDIS_KEY_PREFIX`). Portal pay response adds `payment` + `checkout` objects (legacy `payment_id` / `order_reference` / `provider` retained).

## Postman / Insomnia

Export from `GET /openapi.json` after the app starts, or import the OpenAPI URL directly in the client.
