# nginx (production snippets)

Example reverse proxy for:

- TLS termination
- `/api` → FastAPI upstream
- `/` → Next.js upstream

See `example.conf` — **do not** use as-is in production without hardening (rate limits, real certs, headers).
