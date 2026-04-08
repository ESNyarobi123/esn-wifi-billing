import type { Page } from "@playwright/test";
import { fulfillApiJson, handleCorsPreflight } from "./cors-fulfill";

function isOurApiRequest(url: URL): boolean {
  if (!url.pathname.startsWith("/api/v1/")) return false;
  const port = url.port || (url.protocol === "https:" ? "443" : "80");
  if (port !== "8000") return false;
  const hn = url.hostname;
  return hn === "127.0.0.1" || hn === "localhost" || hn === "::1";
}

function pathMatches(pathname: string, exact: string) {
  return pathname === exact || pathname === `${exact}/`;
}

export type E2eMockOpts = { paymentId?: string };

/**
 * Single catch-all for FastAPI origin so OPTIONS + GET are mocked with CORS
 * (Next dev on :3000 → API on :8000 is cross-origin with Authorization preflight).
 */
export async function installE2eBackendMocks(page: Page, opts: E2eMockOpts = {}) {
  const siteSlug = "demo-site";
  const portalPrefix = `/api/v1/portal/${siteSlug}`;
  const { paymentId } = opts;

  await page.route("**/*", async (route) => {
    const req = route.request();
    let url: URL;
    try {
      url = new URL(req.url());
    } catch {
      return route.continue();
    }
    if (!isOurApiRequest(url)) return route.continue();

    const path = url.pathname;
    const method = req.method();

    if (await handleCorsPreflight(route)) return;

    if (paymentId && pathMatches(path, `/api/v1/payments/${paymentId}/events`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: [
          {
            id: "77777777-7777-7777-7777-777777777777",
            event_type: "payment.created",
            payload: { note: "mock" },
            created_at: new Date().toISOString(),
          },
        ],
      });
      return;
    }

    if (paymentId && pathMatches(path, `/api/v1/payments/${paymentId}`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: {
          id: paymentId,
          order_reference: "ORD-MOCK-1",
          provider: "mock",
          amount: "1000",
          currency: "TZS",
          payment_status: "success",
          provider_ref: null,
          customer_id: "33333333-3333-3333-3333-333333333333",
          plan_id: "44444444-4444-4444-4444-444444444444",
          site_id: null,
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
      return;
    }

    if (pathMatches(path, "/api/v1/routers")) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: [
          {
            id: "11111111-1111-1111-1111-111111111111",
            site_id: "22222222-2222-2222-2222-222222222222",
            name: "Router A",
            host: "10.0.0.1",
            api_port: 8728,
            use_tls: false,
            status: "active",
            is_online: true,
            last_seen_at: new Date().toISOString(),
          },
        ],
      });
      return;
    }

    if (pathMatches(path, "/api/v1/customers")) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: [
          {
            id: "33333333-3333-3333-3333-333333333333",
            full_name: "Test User",
            email: "user@example.com",
            phone: null,
            account_status: "active",
            site_id: null,
          },
        ],
      });
      return;
    }

    if (pathMatches(path, "/api/v1/plans")) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: [
          {
            id: "44444444-4444-4444-4444-444444444444",
            name: "Day pass",
            plan_type: "time",
            price_amount: "5000",
            currency: "TZS",
            is_active: true,
          },
        ],
      });
      return;
    }

    if (pathMatches(path, "/api/v1/auth/me")) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: {
          id: "99999999-9999-9999-9999-999999999999",
          email: "admin@test.local",
          full_name: "Admin",
          is_active: true,
          created_at: new Date().toISOString(),
        },
      });
      return;
    }

    if (pathMatches(path, "/api/v1/sites")) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, { success: true, message: "OK", data: [] });
      return;
    }

    if (pathMatches(path, `${portalPrefix}/branding`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: {
          site: {
            id: "00000000-0000-0000-0000-000000000001",
            name: "Demo Café",
            slug: siteSlug,
          },
          branding: {
            logo_url: null,
            primary_color: "#FBA002",
            welcome_message: "Welcome to Demo Café Wi‑Fi",
            support_phone: null,
            extra: null,
          },
        },
      });
      return;
    }

    if (pathMatches(path, `${portalPrefix}/status`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: {
          site: { name: "Demo Café", slug: siteSlug, timezone: "Africa/Dar_es_Salaam" },
          routers: { total: 2, online: 2 },
        },
      });
      return;
    }

    if (pathMatches(path, `${portalPrefix}/plans`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: [
          {
            id: "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            name: "1 Hour",
            description: "Quick session",
            plan_type: "time",
            price_amount: "1000.00",
            currency: "TZS",
          },
        ],
      });
      return;
    }

    if (pathMatches(path, `${portalPrefix}/access-status`)) {
      if (method !== "GET") return route.continue();
      await fulfillApiJson(route, {
        success: true,
        message: "OK",
        data: {
          site: { id: "x", name: "Demo", slug: siteSlug },
          customer_id: "550e8400-e29b-41d4-a716-446655440000",
          has_usable_access: true,
          primary_access: {
            grant_id: "g1",
            plan_id: "p1",
            plan_name: "1 Hour",
            source: "payment",
            entitlement: { is_usable: true },
          },
          usable_grants: [],
        },
      });
      return;
    }

    return route.continue();
  });
}
