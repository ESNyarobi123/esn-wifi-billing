import type { HotspotContext } from "@/lib/portal/hotspot-context";

export type HotspotContextPayload = {
  mac_address: string | null;
  ip_address: string | null;
  hotspot_server_name: string | null;
  hotspot_login_url: string | null;
  identity: string | null;
  original_destination: string | null;
  router_id: string | null;
  site_id: string | null;
};

export type PortalAuthorization = {
  available: boolean;
  mode?: string;
  router_id?: string;
  router_name?: string;
  mac_address?: string;
  username?: string;
  password?: string;
  profile_name?: string;
  rate_limit?: string | null;
  limit_uptime_seconds?: number | null;
  login_url?: string | null;
  server_name?: string | null;
  destination?: string | null;
  nas?: Record<string, unknown>;
  reason?: string;
};

export function hotspotContextToPayload(context: HotspotContext | null): HotspotContextPayload | null {
  if (!context?.mac_address) return null;
  return {
    mac_address: context.mac_address,
    ip_address: context.ip_address,
    hotspot_server_name: context.server_name,
    hotspot_login_url: context.login_url,
    identity: context.identity,
    original_destination: context.original_destination,
    router_id: context.router_id,
    site_id: context.site_id,
  };
}

export function submitHotspotLogin(auth: PortalAuthorization) {
  if (typeof window === "undefined") return;
  if (!auth.available || !auth.login_url || !auth.username || !auth.password) return;
  const form = document.createElement("form");
  form.method = "POST";
  form.action = auth.login_url;
  form.style.display = "none";
  const fields: Record<string, string> = {
    username: auth.username,
    password: auth.password,
    dst: auth.destination || "",
    popup: "false",
  };
  for (const [key, value] of Object.entries(fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = key;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
  form.remove();
}
