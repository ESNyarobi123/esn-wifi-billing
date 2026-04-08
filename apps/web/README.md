# apps/web — Next.js

Admin console, captive portal, and shared UI.

## Routes

- `src/app/(auth)/login` — operator sign-in  
- `src/app/(dashboard)/dashboard` — admin shell  
- `src/app/(portal)/[siteSlug]` — captive portal  
- `src/app/api` — small Next routes (e.g. `/api/health`)

## Local development

```bash
npm install
npm run dev
```

Copy `.env.example` → `.env.local` and set `NEXT_PUBLIC_API_URL` to your FastAPI origin.

## Staging & standalone production

See **[docs/STAGING.md](./docs/STAGING.md)** for:

- `npm run build:standalone` / `npm run start:standalone`
- `INTERNAL_API_URL` vs `NEXT_PUBLIC_API_URL`
- Docker layout, smoke checks, and troubleshooting

Quick smoke (web must already be running):

```bash
npm run staging:smoke
```

## Tests

```bash
npm run test:e2e        # production-like standalone server + Playwright
npm run test:e2e:dev    # next dev (debug only)
```
