"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiPostPublic } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import { getStoredHotspotContext } from "@/lib/portal/hotspot-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { formatDate } from "@/lib/format";

type SessionStatus = {
  active: boolean;
  session?: {
    login_at: string;
    expires_at: string | null;
    bytes_up: number;
    bytes_down: number;
  };
};

export function PortalSessionStatus({ siteSlug }: { siteSlug: string }) {
  const [mac, setMac] = useState("");
  const [data, setData] = useState<SessionStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [detectedMac, setDetectedMac] = useState<string | null>(null);
  const [didAutoCheck, setDidAutoCheck] = useState(false);

  useEffect(() => {
    const context = getStoredHotspotContext(siteSlug);
    if (!context?.mac_address) return;
    setDetectedMac(context.mac_address);
    setMac((current) => current || context.mac_address || "");
  }, [siteSlug]);

  useEffect(() => {
    if (didAutoCheck || !detectedMac) return;
    setDidAutoCheck(true);
    void check();
  }, [detectedMac, didAutoCheck]);

  async function check(e?: React.FormEvent) {
    e?.preventDefault();
    const macToCheck = (detectedMac || mac).trim();
    if (!macToCheck) {
      toast.error("Enter your device MAC address (Wi‑Fi address).");
      return;
    }
    setBusy(true);
    setData(null);
    try {
      const res = await apiPostPublic<SessionStatus>(`/portal/${siteSlug}/session-status`, { mac_address: macToCheck });
      setData(res);
      if (!res.active) {
        toast.message("No active session found for this device.");
      }
    } catch (err) {
      toast.error(userFacingApiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PortalCustomerBanner siteSlug={siteSlug} />
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Session status</h1>
        <p className="mt-2 text-pretty text-sm text-white/75">We&apos;ll check this device automatically. You only need a MAC address for support cases.</p>
      </div>
      <Card className="border-white/10 bg-white/5 text-white">
        <CardHeader>
          <CardTitle className="text-base font-display">Current device</CardTitle>
        </CardHeader>
        <CardContent>
          {detectedMac && (
            <div className="mb-4 rounded-xl border border-[var(--portal-accent)]/30 bg-black/30 p-3 text-sm text-white/85">
              This hotspot device was detected automatically: <span className="font-mono text-xs">{detectedMac}</span>
            </div>
          )}
          {detectedMac ? (
            <div className="space-y-4">
              <Button
                type="button"
                disabled={busy}
                className="min-h-12 w-full font-semibold text-slate-900 sm:w-auto"
                style={{ backgroundColor: "var(--portal-accent)" }}
                onClick={() => void check()}
              >
                {busy ? "Checking…" : "Refresh session"}
              </Button>
              <details className="rounded-xl border border-white/10 bg-black/20 p-4">
                <summary className="cursor-pointer text-sm font-medium text-white">Use another MAC address</summary>
                <form className="mt-4 space-y-4" onSubmit={check}>
                  <div className="space-y-2">
                    <Label htmlFor="session-mac" className="text-white/85">
                      MAC address
                    </Label>
                    <Input
                      id="session-mac"
                      className="min-h-11 border-white/20 bg-black/30 font-mono text-sm text-white"
                      value={mac}
                      onChange={(e) => setMac(e.target.value)}
                      placeholder="AA:BB:CC:DD:EE:FF"
                      autoComplete="off"
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={busy}
                    className="min-h-11 w-full font-semibold text-slate-900 sm:w-auto"
                    style={{ backgroundColor: "var(--portal-accent)" }}
                  >
                    {busy ? "Checking…" : "Look up another MAC"}
                  </Button>
                </form>
              </details>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={check}>
              <div className="space-y-2">
                <Label htmlFor="session-mac" className="text-white/85">
                  MAC address
                </Label>
                <Input
                  id="session-mac"
                  className="min-h-11 border-white/20 bg-black/30 font-mono text-sm text-white"
                  value={mac}
                  onChange={(e) => setMac(e.target.value)}
                  placeholder="AA:BB:CC:DD:EE:FF"
                  autoComplete="off"
                />
              </div>
              <Button
                type="submit"
                disabled={busy}
                className="min-h-12 w-full font-semibold text-slate-900 sm:w-auto"
                style={{ backgroundColor: "var(--portal-accent)" }}
              >
                {busy ? "Checking…" : "Look up session"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
      {data && (
        <Card className="border-white/10 bg-black/30 text-white">
          <CardContent className="space-y-4 pt-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-white/70">Session active</span>
              <Badge
                variant={data.active ? "success" : "secondary"}
                aria-label={data.active ? "Session active: yes" : "Session active: no"}
              >
                {data.active ? "Yes" : "No"}
              </Badge>
            </div>
            {data.session && (
              <dl className="grid gap-3 rounded-xl border border-white/10 bg-black/25 p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-white/55">Signed in</dt>
                  <dd className="mt-0.5 font-medium">{formatDate(data.session.login_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-white/55">Expires</dt>
                  <dd className="mt-0.5 font-medium">{data.session.expires_at ? formatDate(data.session.expires_at) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-white/55">Bytes up</dt>
                  <dd className="mt-0.5 font-mono text-xs">{data.session.bytes_up}</dd>
                </div>
                <div>
                  <dt className="text-xs text-white/55">Bytes down</dt>
                  <dd className="mt-0.5 font-mono text-xs">{data.session.bytes_down}</dd>
                </div>
              </dl>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
