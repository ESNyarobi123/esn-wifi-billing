export type HotspotContext = {
  mac_address: string | null;
  ip_address: string | null;
  server_name: string | null;
  identity: string | null;
  login_url: string | null;
  status_url: string | null;
  original_destination: string | null;
  router_id: string | null;
  site_id: string | null;
  captured_at: string;
};

const KEY = (slug: string) => `esn_portal_hotspot_${slug}`;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function normalizeMac(value: string | null): string | null {
  if (!value) return null;
  const cleaned = value.trim().replace(/-/g, ":").toUpperCase();
  return cleaned || null;
}

function normalizeUuid(value: string | null): string | null {
  if (!value) return null;
  const cleaned = value.trim();
  return UUID_RE.test(cleaned) ? cleaned : null;
}

export function captureHotspotContext(siteSlug: string, search: URLSearchParams): HotspotContext | null {
  if (typeof window === "undefined") return null;
  const context: HotspotContext = {
    mac_address: normalizeMac(search.get("hs_mac")),
    ip_address: search.get("hs_ip")?.trim() || null,
    server_name: search.get("hs_server")?.trim() || null,
    identity: search.get("hs_identity")?.trim() || null,
    login_url: search.get("hs_login_url")?.trim() || null,
    status_url: search.get("hs_status_url")?.trim() || null,
    original_destination: search.get("hs_dst")?.trim() || null,
    router_id: normalizeUuid(search.get("esn_router_id")),
    site_id: normalizeUuid(search.get("esn_site_id")),
    captured_at: new Date().toISOString(),
  };
  if (!context.mac_address && !context.ip_address && !context.server_name) return null;
  window.localStorage.setItem(KEY(siteSlug), JSON.stringify(context));
  return context;
}

export function getStoredHotspotContext(siteSlug: string): HotspotContext | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY(siteSlug));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as HotspotContext;
    return {
      ...parsed,
      mac_address: normalizeMac(parsed.mac_address),
      router_id: normalizeUuid(parsed.router_id),
      site_id: normalizeUuid(parsed.site_id),
    };
  } catch {
    return null;
  }
}

export function clearStoredHotspotContext(siteSlug: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY(siteSlug));
}
