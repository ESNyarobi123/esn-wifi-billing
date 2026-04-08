# Staging & production — Next.js standalone (`apps/web`)

This app uses [`output: "standalone"`](../next.config.ts). The runnable server is **`server.js` inside `.next/standalone/`**, not `next start` (Next logs a warning if you use `next start` with standalone enabled).

## What gets built

After `next build`:

| Path | Role |
|------|------|
| `.next/standalone/` | Minimal Node server (`server.js`), traced `node_modules`, server chunks |
| `.next/static/` | Client JS/CSS chunks — **not** embedded in `standalone` by default |
| `public/` | Static files served as `/…` |

**You must copy** `.next/static` and `public` into the standalone tree before running `server.js` (same layout as the official Docker example).

This repo automates that with:

```bash
npm run build:standalone   # next build && node scripts/prepare-standalone.mjs
```

## Run locally (production mode)

```bash
export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000   # or your API; affects client bundle at build time
npm run build:standalone
export PORT=3000
export HOSTNAME=0.0.0.0
# Optional: SSR-only override when API hostname differs from the browser (Docker, private network)
# export INTERNAL_API_URL=http://api:8000
npm run start:standalone
```

`start:standalone` runs `node server.js` with `cwd` = `.next/standalone` (see `scripts/run-standalone.mjs`).

## Environment variables

| Variable | When | Purpose |
|----------|------|---------|
| `NEXT_PUBLIC_API_URL` | **Build time** for client JS; also read on server if `INTERNAL_API_URL` unset | Origin the **browser** uses for `/api/v1/...` (no trailing slash) |
| `INTERNAL_API_URL` | **Runtime**, server only | Origin for **SSR/RSC** fetches (portal branding in `(portal)/[siteSlug]/layout.tsx`). Use Docker service DNS (e.g. `http://api:8000`) so the container does not call `localhost:8000` by mistake |

**Important:** Changing `NEXT_PUBLIC_*` after build does **not** update inlined client bundles. Rebuild the web image (or run `next build` again) if the public API URL changes.

**Docker Compose (local):** `docker-compose.yml` passes `build.args.NEXT_PUBLIC_API_URL` for the bake and sets `INTERNAL_API_URL=http://api:8000` at runtime for the `web` service.

## Docker

- **Dockerfile:** multi-stage build; builder runs `npm run build && node scripts/prepare-standalone.mjs`; runner copies `public`, `.next/standalone`, and `.next/static` (mirrors Next’s documented layout).
- **Build arg:** `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **`.dockerignore`:** excludes `node_modules`, `.next`, e2e artifacts, etc., so context stays small.

Staging behind a public hostname: rebuild with e.g.

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.staging.example.com -t esn-web:staging ./apps/web
```

## Smoke verification

With the web process listening:

```bash
BASE_URL=http://127.0.0.1:3000 npm run staging:smoke
# Optional: also probe FastAPI (tries common health paths)
BASE_URL=http://127.0.0.1:3000 API_PUBLIC_URL=http://127.0.0.1:8000 npm run staging:smoke
# Portal path: default slug is `hq` (demo seed). Override if your staging site differs:
# PORTAL_SLUG=my-site BASE_URL=https://web.staging.example.com API_PUBLIC_URL=https://api.staging.example.com npm run staging:smoke
# No portal / empty DB: SKIP_PORTAL_CHECK=1 npm run staging:smoke
```

The script checks: login page, Next `/api/health` (JSON shape), home, **dashboard auth redirects** (unauthenticated → login), portal `/{PORTAL_SLUG}`, and optionally API liveness.

**Full UAT / RC:** see repo [`docs/UAT_CHECKLIST.md`](../../docs/UAT_CHECKLIST.md) and [`docs/RELEASE_CANDIDATE.md`](../../docs/RELEASE_CANDIDATE.md).

### Manual checklist

- [ ] `GET /login` → 200, sign-in UI loads; static assets (fonts, `_next/static`) return 200
- [ ] `GET /api/health` → JSON `{ ok: true, service: "esn-wifi-web" }`
- [ ] `GET /` → redirect or 200 as expected with session cookie rules
- [ ] `GET /{siteSlug}` (portal) → 200 shell; branding banner matches API reachability (demo seed uses slug **`hq`**)
- [ ] Browser devtools: XHR/fetch target `NEXT_PUBLIC_API_URL` (not an unexpected host)
- [ ] **Docker:** from host, portal page view-source or logs show SSR can reach API via `INTERNAL_API_URL` (no permanent “degraded branding” when API is up)

## Playwright E2E vs real staging

- **`npm run test:e2e`** (default): `build:standalone` + `start:standalone` so behavior matches Docker/staging (no Turbopack HMR under automation).
- **`npm run test:e2e:dev`:** `next dev` for debugging only; flaky for API mocks.

See `playwright.config.ts` and root `.env.example` / `apps/web/.env.example`.

## Common failures

| Symptom | Likely cause |
|---------|----------------|
| 404 on `/_next/static/...` | Forgot `prepare-standalone.mjs` or Docker didn’t copy `.next/static` |
| Portal always “degraded” / wrong branding in Docker | SSR using `localhost` for API; set `INTERNAL_API_URL` to service URL |
| Browser can’t call API | Wrong `NEXT_PUBLIC_API_URL` **at build**; CORS on FastAPI (`CORS_ORIGINS`) |
| `next start` warns about standalone | Expected; use `start:standalone` or `node server.js` in `.next/standalone` |

## Rollback / restart

- **Container:** redeploy previous image tag; `INTERNAL_API_URL` / `PORT` / `HOSTNAME` are safe to change without rebuild.
- **Client API host wrong:** must **rebuild** web with correct `NEXT_PUBLIC_API_URL`.

## Next.js middleware → proxy

Next 16 deprecates the `middleware` file convention in favor of **`proxy`**. This app still uses `middleware.ts` for dashboard auth gating. Plan a migration when upgrading; it does not block standalone deployment — see Next upgrade guide.
