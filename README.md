# ESN WiFi Billing System — monorepo

```
esn-wifi-billing/
├── apps/web/          Next.js (admin + captive portal)
├── services/api/      FastAPI + Celery workers
├── infra/nginx/       Production reverse-proxy snippets
└── scripts/           Demo seeds and tooling
```

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY and ROUTER_CREDENTIALS_FERNET_KEY for real use.
# Keep SEED_DEMO_DATA=false for an empty business dataset (add routers/plans/customers in the UI).
# Use SEED_DEMO_DATA=true only when running `python -m app.seed` for a filled demo workshop DB.
docker compose up --build
```

- **Web:** http://localhost:3000  
- **API:** http://localhost:8000  
- **API docs:** http://localhost:8000/docs  

Local override: copy `docker-compose.override.yml.example` to `docker-compose.override.yml`.

**Stack:** Next.js 16 (App Router), FastAPI, Celery, PostgreSQL, Redis.

## Structure

See nested `README.md` files in `apps/web` and `services/api` for stack-specific details.

### Staging / standalone Next.js

The web app ships as a **standalone** Node bundle (`server.js` under `.next/standalone/`). Build/run and Docker notes live in [`apps/web/docs/STAGING.md`](apps/web/docs/STAGING.md).

**Release candidate / UAT:** [`docs/UAT_CHECKLIST.md`](docs/UAT_CHECKLIST.md) (manual flows), [`docs/RELEASE_CANDIDATE.md`](docs/RELEASE_CANDIDATE.md) (env, migrations, rollback, known limitations). From `apps/web`: `npm run staging:smoke` against your deployed `BASE_URL` (+ optional `API_PUBLIC_URL`).

**Production VPS + router onboarding:** [`docs/VPS_PRODUCTION_AND_ROUTER_ONBOARDING.md`](docs/VPS_PRODUCTION_AND_ROUTER_ONBOARDING.md) — public domain setup, env checklist, and end-to-end MikroTik provisioning flow.

**Spotbox runbook (Swahili):** [`docs/SPOTBOX_REMOTE_ROUTER_RUNBOOK_SW.md`](docs/SPOTBOX_REMOTE_ROUTER_RUNBOOK_SW.md) and [`docs/SPOTBOX_REMOTE_ROUTER_RUNBOOK_SW.docx`](docs/SPOTBOX_REMOTE_ROUTER_RUNBOOK_SW.docx) — VPS, WireGuard, remote router onboarding, provisioning, and troubleshooting.
