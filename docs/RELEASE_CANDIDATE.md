# Release candidate — ESN WiFi Billing

This document supports **staging validation** and **launch-preview** sign-off. It is not a substitute for running the app against your real staging stack.

---

## 1. Pre-release verification

### 1.1 Environment variables

**API (FastAPI)**

| Variable | Confirm |
|----------|---------|
| `DATABASE_URL` | Points at staging DB; uses correct driver (`postgresql+asyncpg://…`) |
| `REDIS_URL` | Reachable; same DB index convention as Celery |
| `JWT_SECRET_KEY` | Strong secret; not copied from dev |
| `CORS_ORIGINS` | **Exact** comma-separated origins for admin UI and portal (scheme + host + port). LAN or staging hostnames must be listed explicitly. |
| `TRUSTED_HOSTS` | Set when API is behind a public hostname / TLS terminator (see `BACKEND_ROLLOUT.md`) |
| Payment provider secrets | Mock vs real provider matches staging policy |
| `ROUTER_CREDENTIALS_FERNET_KEY` | Set if storing live router credentials |
| Portal rate limits | `PORTAL_RATE_LIMIT_*` appropriate for staging load |

**Web (Next.js)**

| Variable | Confirm |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | **Baked at build** — public origin browsers use for `/api/v1/...` (no trailing slash) |
| `INTERNAL_API_URL` | **Runtime** — server-side fetches (portal branding, RSC). In Docker: service DNS (e.g. `http://api:8000`), not `localhost` |

### 1.2 Database

- [ ] `alembic upgrade head` applied on staging DB  
- [ ] Optional: compare `alembic current` to expected revision  
- [ ] Seed scripts (`python -m app.seed`) only where appropriate — **never** on production without policy  

### 1.3 Process health

- [ ] API: `/api/v1/health/live` (and readiness if you use it)  
- [ ] Celery worker + beat running if you rely on background jobs / reconciliation  
- [ ] Web: `GET /api/health` on Next returns `esn-wifi-web`  

### 1.4 Frontend artifacts

- [ ] Standalone layout: `.next/static` and `public` present next to `server.js` (see [`apps/web/docs/STAGING.md`](../apps/web/docs/STAGING.md))  
- [ ] After changing `NEXT_PUBLIC_*`, web image **rebuilt**  

### 1.5 Automated checks

- [ ] `cd apps/web && npm run staging:smoke` against staging `BASE_URL` (+ `API_PUBLIC_URL`, correct `PORTAL_SLUG`)  
- [ ] `cd apps/web && npm run test:e2e` on a clean environment before tagging RC (baseline; adjust if staging differs)  

### 1.6 UAT

- [ ] [`UAT_CHECKLIST.md`](UAT_CHECKLIST.md) completed for this candidate  

---

## 2. Rollback and startup notes

**Web (container)**

- Roll back: deploy previous image tag.  
- Runtime-only env changes: `INTERNAL_API_URL`, `PORT`, `HOSTNAME` do **not** require rebuild.  
- Wrong API host in **browser**: fix `NEXT_PUBLIC_API_URL` and **rebuild** web.

**API**

- Roll back: previous image + DB migration strategy (prefer **forward-only** migrations; avoid `alembic downgrade` on shared staging unless planned).  
- Document the last known-good API revision alongside the RC tag.

**Database**

- Backup before RC migration if staging holds important data.

---

## 3. Demo / walkthrough capture (optional but recommended)

- Short screen recording or screenshots: login → dashboard → one router page → one portal pay/redeem path  
- Note staging URL, build SHA/tag, and time (timezone)  

---

## 4. Known limitations (template)

_Edit per release._

| Area | Limitation | Workaround / ETA |
|------|------------|-------------------|
| MikroTik | Real adapter / REST stub flags | Document `MIKROTIK_USE_MOCK` vs live |
| Payments | Mock vs ClickPesa sandbox | |
| Portal | Rate limits / Redis fail-open behavior | See `BACKEND_ROLLOUT.md` |
| CORS | Must list every browser origin | Add staging hostname to `CORS_ORIGINS` |

---

## 5. Definition of done (RC)

- [ ] Staging stack runs current candidate with real services  
- [ ] No P0/P1 bugs open for demo scope  
- [ ] Env, migrations, and smoke/UAT documented above  
- [ ] Rollback path agreed for web + API  

---

## Related docs

- [`apps/web/docs/STAGING.md`](../apps/web/docs/STAGING.md) — standalone Next.js, Docker, smoke command  
- [`services/api/docs/BACKEND_ROLLOUT.md`](../services/api/docs/BACKEND_ROLLOUT.md) — backend hardening  
- [`UAT_CHECKLIST.md`](UAT_CHECKLIST.md) — manual flow validation  
