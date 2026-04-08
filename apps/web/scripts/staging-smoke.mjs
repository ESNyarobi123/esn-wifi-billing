#!/usr/bin/env node
/**
 * Lightweight HTTP smoke checks for a running web instance (local Docker, staging, etc.).
 *
 * Usage:
 *   BASE_URL=http://127.0.0.1:3000 node scripts/staging-smoke.mjs
 *   BASE_URL=http://127.0.0.1:3000 API_PUBLIC_URL=http://127.0.0.1:8000 node scripts/staging-smoke.mjs
 *
 * Environment:
 *   BASE_URL          — Next.js origin (default http://127.0.0.1:3000)
 *   API_PUBLIC_URL    — Optional FastAPI origin; probes health under /api/v1/health/*
 *   PORTAL_SLUG       — Site slug for portal shell (default "hq", matches `app.seed` demo site)
 *   SKIP_PORTAL_CHECK — If "1" or "true", skip portal route (e.g. empty DB / custom seed)
 */
const base = (process.env.BASE_URL || "http://127.0.0.1:3000").replace(/\/$/, "");
const apiPublic = (process.env.API_PUBLIC_URL || "").replace(/\/$/, "");
const portalSlug = (process.env.PORTAL_SLUG || "hq").trim();
const skipPortal = ["1", "true", "yes"].includes(
  (process.env.SKIP_PORTAL_CHECK || "").toLowerCase(),
);

/** @type {{ name: string; path: string; expectStatus: number[] }[]} */
const checks = [
  { name: "login page", path: "/login", expectStatus: [200] },
  { name: "Next health", path: "/api/health", expectStatus: [200] },
  { name: "home redirects or loads", path: "/", expectStatus: [200, 302, 307, 308] },
  {
    name: "dashboard auth gate (redirect to login)",
    path: "/dashboard",
    expectStatus: [302, 307, 308],
  },
  {
    name: "dashboard sub-route auth gate",
    path: "/dashboard/plans",
    expectStatus: [302, 307, 308],
  },
];

if (!skipPortal && portalSlug) {
  checks.push({
    name: `portal shell /${portalSlug}`,
    path: `/${portalSlug}`,
    expectStatus: [200],
  });
}

async function getStatus(url) {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 15_000);
  try {
    const res = await fetch(url, { method: "GET", redirect: "manual", signal: ac.signal });
    return res;
  } finally {
    clearTimeout(t);
  }
}

let failed = 0;
for (const c of checks) {
  const url = `${base}${c.path}`;
  try {
    const res = await getStatus(url);
    const status = res.status;
    if (!c.expectStatus.includes(status)) {
      console.error(`FAIL ${c.name}: ${url} → ${status} (expected one of ${c.expectStatus.join(",")})`);
      failed++;
    } else {
      console.log(`ok   ${c.name}: ${status} ${url}`);
    }

    if (c.path === "/api/health" && status === 200) {
      try {
        const body = await res.clone().json();
        if (body?.ok !== true || body?.service !== "esn-wifi-web") {
          console.error(
            `FAIL Next health body: expected { ok: true, service: "esn-wifi-web" }, got ${JSON.stringify(body)}`,
          );
          failed++;
        }
      } catch (e) {
        console.error(`FAIL Next health JSON: ${e instanceof Error ? e.message : e}`);
        failed++;
      }
    }
  } catch (e) {
    console.error(`FAIL ${c.name}: ${url} → ${e instanceof Error ? e.message : e}`);
    failed++;
  }
}

if (apiPublic) {
  const paths = ["/api/v1/health/live", "/api/v1/health/ready", "/health", "/docs"];
  let apiOk = false;
  for (const p of paths) {
    try {
      const res = await getStatus(`${apiPublic}${p}`);
      const status = res.status;
      if (status >= 200 && status < 400) {
        console.log(`ok   API probe: ${status} ${apiPublic}${p}`);
        apiOk = true;
        break;
      }
    } catch {
      /* try next path */
    }
  }
  if (!apiOk) {
    console.error(`FAIL API: could not reach a known health path under ${apiPublic}`);
    failed++;
  }
}

if (failed) {
  console.error(`\nstaging-smoke: ${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nstaging-smoke: all checks passed");
