"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { apiGetPublic } from "@/lib/api/client";
import type { PortalAccessStatus } from "@/lib/api/types";
import { isRateLimitedError, userFacingApiMessage } from "@/lib/api/error-utils";
import { getStoredCustomerId, setStoredCustomerId } from "@/lib/portal/customer-storage";
import { getStoredHotspotContext } from "@/lib/portal/hotspot-context";
import { submitHotspotLogin } from "@/lib/portal/router-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { PortalInlineError } from "@/components/portal/portal-inline-error";

export function PortalAccess({ siteSlug }: { siteSlug: string }) {
  const [customerId, setCustomerId] = useState("");
  const [data, setData] = useState<PortalAccessStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<Error | null>(null);
  const [detectedMac, setDetectedMac] = useState<string | null>(null);
  const [didAutoCheck, setDidAutoCheck] = useState(false);

  useEffect(() => {
    const s = getStoredCustomerId(siteSlug);
    if (s) setCustomerId(s);
    const context = getStoredHotspotContext(siteSlug);
    if (context?.mac_address) setDetectedMac(context.mac_address);
  }, [siteSlug]);

  useEffect(() => {
    if (didAutoCheck) return;
    if (!customerId.trim() && !detectedMac) return;
    setDidAutoCheck(true);
    void load();
  }, [customerId, detectedMac, didAutoCheck]);

  async function load(e?: React.FormEvent) {
    e?.preventDefault();
    const context = getStoredHotspotContext(siteSlug);
    if (!customerId.trim() && !context?.mac_address) {
      toast.error("Enter your customer ID or open this page from the hotspot device you used.");
      return;
    }
    setLoading(true);
    setErr(null);
    setData(null);
    try {
      const params = new URLSearchParams();
      if (customerId.trim()) params.set("customer_id", customerId.trim());
      if (context?.mac_address) params.set("mac_address", context.mac_address);
      if (context?.router_id) params.set("router_id", context.router_id);
      if (context?.login_url) params.set("hotspot_login_url", context.login_url);
      if (context?.server_name) params.set("hotspot_server_name", context.server_name);
      if (context?.ip_address) params.set("ip_address", context.ip_address);
      if (context?.identity) params.set("identity", context.identity);
      if (context?.original_destination) params.set("hs_dst", context.original_destination);

      const res = await apiGetPublic<PortalAccessStatus>(`/portal/${siteSlug}/access-status?${params.toString()}`);
      if (customerId.trim()) setStoredCustomerId(siteSlug, customerId.trim());
      setData(res);
    } catch (error) {
      setErr(error as Error);
      toast.error(userFacingApiMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PortalCustomerBanner siteSlug={siteSlug} />
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Your access</h1>
        <p className="mt-2 text-pretty text-sm text-white/75">We&apos;ll check this hotspot device first. Only use a customer ID if staff asked you to.</p>
      </div>

      {detectedMac && (
        <div className="rounded-xl border border-[var(--portal-accent)]/30 bg-black/25 p-3 text-sm text-white/85">
          Detected hotspot device. We&apos;re using it automatically for the access check.
        </div>
      )}

      {err && (
        <PortalInlineError
          title={isRateLimitedError(err) ? "Please wait a moment" : "Couldn’t load access"}
          description={userFacingApiMessage(err)}
          variant={isRateLimitedError(err) ? "rate_limit" : "generic"}
          onRetry={() => {
            setErr(null);
            void load();
          }}
        />
      )}

      {detectedMac ? (
        <details className="rounded-xl border border-white/10 bg-white/5 p-4 text-white">
          <summary className="cursor-pointer text-sm font-medium text-white">Use a customer ID instead</summary>
          <form className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={load}>
            <div className="min-w-0 flex-1 space-y-2">
              <Label htmlFor="access-customer" className="text-white/85">
                Customer ID <span className="text-white/45">(support only)</span>
              </Label>
              <Input
                id="access-customer"
                className="min-h-11 border-white/20 bg-black/30 font-mono text-xs text-white"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                autoComplete="off"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="min-h-11 text-slate-900 sm:w-auto"
              style={{ backgroundColor: "var(--portal-accent)" }}
            >
              {loading ? "Checking…" : "Retry check"}
            </Button>
          </form>
        </details>
      ) : (
        <Card className="border-white/10 bg-white/5 text-white">
          <CardContent className="pt-6">
            <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={load}>
              <div className="min-w-0 flex-1 space-y-2">
                <Label htmlFor="access-customer" className="text-white/85">
                  Customer ID
                </Label>
                <Input
                  id="access-customer"
                  className="min-h-11 border-white/20 bg-black/30 font-mono text-xs text-white"
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <Button
                type="submit"
                disabled={loading}
                className="min-h-11 text-slate-900 sm:w-auto"
                style={{ backgroundColor: "var(--portal-accent)" }}
              >
                {loading ? "Checking…" : "Check status"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {data && (
        <Card className="border-white/10 bg-black/30 text-white">
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2 text-base font-display">
              Summary
              <Badge
                variant={data.has_usable_access ? "success" : "destructive"}
                aria-label={data.has_usable_access ? "Access status: active" : "Access status: no usable access"}
              >
                {data.has_usable_access ? "Active" : "No access"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {data.resolved_by && (
              <p className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70">
                Resolved using: <span className="font-medium text-white">{data.resolved_by}</span>
              </p>
            )}
            {data.primary_access ? (
              <section className="rounded-xl border border-white/10 bg-white/5 p-4" aria-labelledby="access-primary-heading">
                <h2 id="access-primary-heading" className="font-medium text-white">
                  Current plan
                </h2>
                <p className="mt-1 text-white/75">{data.primary_access.plan_name ?? "Plan"}</p>
                <p className="mt-1 text-xs text-white/55">Added via {data.primary_access.source}</p>
                <dl className="mt-3 space-y-2 border-t border-white/10 pt-3 text-xs text-white/80">
                  {Object.entries(data.primary_access.entitlement).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4">
                      <dt className="text-white/55">{k}</dt>
                      <dd className="max-w-[60%] truncate font-mono">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : (
              <div className="space-y-3">
                <p className="text-white/70">No paid access is active on this device yet.</p>
                <div className="flex flex-wrap gap-3">
                  <Button
                    asChild
                    className="min-h-11 text-slate-900"
                    style={{ backgroundColor: "var(--portal-accent)" }}
                  >
                    <Link href={`/${siteSlug}/pay`}>Buy a plan</Link>
                  </Button>
                  <Button asChild variant="outline" className="min-h-11 border-white/20 bg-white/5 text-white hover:bg-white/10">
                    <Link href={`/${siteSlug}/redeem`}>Use a voucher</Link>
                  </Button>
                </div>
              </div>
            )}
            {data.usable_grants.length > 1 && (
              <section aria-label="All usable grants">
                <p className="mb-2 font-medium text-white/85">All usable grants</p>
                <ul className="space-y-2">
                  {data.usable_grants.map((g) => (
                    <li key={g.grant_id} className="rounded-lg border border-white/10 px-3 py-2 text-xs">
                      <span className="text-white/90">{g.plan_name}</span>{" "}
                      <span className="text-white/50">({g.source})</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {data.authorization?.available && data.authorization.login_url && data.authorization.username && data.authorization.password && (
              <section className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-4">
                <p className="text-sm font-medium text-white">This device can be connected now.</p>
                <p className="mt-1 text-xs text-white/75">
                  Router: {data.authorization.router_name ?? "HotSpot"}{data.authorization.rate_limit ? ` • Rate ${data.authorization.rate_limit}` : ""}
                </p>
                <Button
                  type="button"
                  className="mt-3 min-h-11 text-slate-900"
                  style={{ backgroundColor: "var(--portal-accent)" }}
                  onClick={() => submitHotspotLogin(data.authorization!)}
                >
                  Connect this device
                </Button>
              </section>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
