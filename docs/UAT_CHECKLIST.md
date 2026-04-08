# UAT / demo checklist — ESN WiFi Billing

Use this for stakeholder demos, staging sign-off, and regression passes after deploys.  
Record **pass/fail**, **browser/device**, **URL**, and **notes** (especially for failures).

**Prerequisites:** API and web reachable; database migrated (`alembic upgrade head`); seed or real data loaded if flows require it; `CORS_ORIGINS` includes the exact admin/portal origin you use (scheme + host + port).

---

## 1. Environment sanity

| Step | Check |
|------|--------|
| 1.1 | Open API docs or `GET /api/v1/health/live` — **200** |
| 1.2 | Open web `GET /api/health` — JSON `ok: true`, `service: "esn-wifi-web"` |
| 1.3 | Browser DevTools → Network: `/api/v1/...` calls go to **expected public API host** (`NEXT_PUBLIC_API_URL`), not an internal-only hostname |
| 1.4 | Portal page “view source” or server logs: SSR can load branding (no stuck “degraded” state when API is healthy and `INTERNAL_API_URL` is correct in Docker) |

Automated subset: from `apps/web`, run  
`BASE_URL=… API_PUBLIC_URL=… PORTAL_SLUG=… npm run staging:smoke`  
(see [`apps/web/docs/STAGING.md`](../apps/web/docs/STAGING.md)).

---

## 2. Admin — authentication

| Step | Check |
|------|--------|
| 2.1 | `/login` loads; validation messages for empty/wrong fields |
| 2.2 | Valid admin sign-in succeeds; redirected toward dashboard (or `next` param) |
| 2.3 | Invalid password shows API error (no silent failure) |
| 2.4 | Sign out clears session; `/dashboard` redirects to `/login` |
| 2.5 | Deep link while logged out: `/dashboard/plans` → login with `next` preserved → lands on plans after login |

---

## 3. Admin — overview dashboard

| Step | Check |
|------|--------|
| 3.1 | `/dashboard` loads without console errors |
| 3.2 | KPIs / charts match API data (spot-check one number against API or DB if needed) |
| 3.3 | Loading and empty states look correct |

---

## 4. Admin — routers

| Step | Check |
|------|--------|
| 4.1 | `/dashboard/routers` lists routers (or empty state) |
| 4.2 | Router detail `/dashboard/routers/{id}` loads |
| 4.3 | Status / snapshots / sessions sub-pages load (**staging:** use read-only or safe actions only) |
| 4.4 | Any “sync” or destructive action follows your staging safety policy |

---

## 5. Admin — customers

| Step | Check |
|------|--------|
| 5.1 | `/dashboard/customers` list loads |
| 5.2 | Customer detail `/dashboard/customers/{id}` loads |
| 5.3 | Related subscriptions / access ties display consistently |

---

## 6. Admin — plans & vouchers

| Step | Check |
|------|--------|
| 6.1 | `/dashboard/plans` list loads |
| 6.2 | Create plan `/dashboard/plans/new` — submit validation and success path |
| 6.3 | Edit plan `/dashboard/plans/{id}` — save works |
| 6.4 | `/dashboard/vouchers` batches list loads |
| 6.5 | Batch detail `/dashboard/vouchers/batches/{id}` loads |
| 6.6 | Admin redeem page `/dashboard/vouchers/redeem` if used |

---

## 7. Admin — payments & sessions

| Step | Check |
|------|--------|
| 7.1 | `/dashboard/payments` list loads |
| 7.2 | Payment detail `/dashboard/payments/{id}` — timeline / events |
| 7.3 | `/dashboard/sessions` if applicable |

---

## 8. Admin — settings

| Step | Check |
|------|--------|
| 8.1 | `/dashboard/settings` loads |
| 8.2 | Persisted settings survive refresh (where applicable) |

---

## 9. Captive portal (public)

Use your real seeded **`siteSlug`** (demo seed defaults to **`hq`** — `https://{web}/{slug}/…`).

| Step | Check |
|------|--------|
| 9.1 | `/{siteSlug}` home — branding (title, colors) matches site config |
| 9.2 | `/{siteSlug}/plans` — plans list loads |
| 9.3 | `/{siteSlug}/pay` — initiate payment (mock or sandbox per policy); confirmation handled |
| 9.4 | `/{siteSlug}/redeem` — redeem flow with test voucher |
| 9.5 | `/{siteSlug}/access` — access status |
| 9.6 | `/{siteSlug}/session` — session status |

---

## 10. Mobile / responsive

| Step | Check |
|------|--------|
| 10.1 | Portal key pages usable on narrow viewport (375px width) |
| 10.2 | Admin: critical tables readable or scrollable without layout break |

---

## 11. Sign-off

| Item | Done |
|------|------|
| Staging URLs and version/build recorded | |
| Failures logged with screenshots / HAR if needed | |
| Known limitations copied to [`RELEASE_CANDIDATE.md`](RELEASE_CANDIDATE.md) | |

---

## Reference

- Staging build & env: [`../apps/web/docs/STAGING.md`](../apps/web/docs/STAGING.md)
- Backend rollout: [`../services/api/docs/BACKEND_ROLLOUT.md`](../services/api/docs/BACKEND_ROLLOUT.md)
