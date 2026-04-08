"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiPostPublic } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import { getStoredCustomerId, setStoredCustomerId } from "@/lib/portal/customer-storage";
import { getStoredHotspotContext } from "@/lib/portal/hotspot-context";
import { hotspotContextToPayload, submitHotspotLogin, type PortalAuthorization } from "@/lib/portal/router-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";

export function PortalRedeem({ siteSlug }: { siteSlug: string }) {
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [authorization, setAuthorization] = useState<PortalAuthorization | null>(null);
  const [detectedMac, setDetectedMac] = useState<string | null>(null);

  useEffect(() => {
    const s = getStoredCustomerId(siteSlug);
    if (s) setCustomerId(s);
    const context = getStoredHotspotContext(siteSlug);
    if (context?.mac_address) setDetectedMac(context.mac_address);
  }, [siteSlug]);

  async function redeem(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) {
      toast.error("Enter the voucher code printed on your card or receipt.");
      return;
    }
    setBusy(true);
    setResult(null);
    setAuthorization(null);
    try {
      const res = await apiPostPublic<{ authorization?: PortalAuthorization | null } & Record<string, unknown>>(`/portal/${siteSlug}/redeem`, {
        code: code.trim(),
        pin: pin.trim() || null,
        customer_id: customerId.trim() || null,
        hotspot_context: hotspotContextToPayload(getStoredHotspotContext(siteSlug)),
      });
      if (customerId.trim()) setStoredCustomerId(siteSlug, customerId.trim());
      setResult(res);
      setAuthorization(res.authorization ?? null);
      toast.success("Redemption complete — check Access to confirm your plan.");
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
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Redeem voucher</h1>
        <p className="mt-2 text-pretty text-sm text-white/75">Enter the code on your voucher. Only add extra details if staff asked for them.</p>
      </div>
      {detectedMac && (
        <div className="rounded-xl border border-[var(--portal-accent)]/30 bg-black/25 p-3 text-sm text-white/85">
          This device was detected automatically. We&apos;ll attach the voucher to this hotspot in the background.
        </div>
      )}
      <Card className="border-white/10 bg-white/5 text-white">
        <CardHeader>
          <CardTitle className="text-base font-display">Voucher code</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={redeem}>
            <div className="space-y-2">
              <Label htmlFor="redeem-code" className="text-white/85">
                Code <span className="text-rose-300">*</span>
              </Label>
              <Input
                id="redeem-code"
                className="min-h-11 border-white/20 bg-black/30 font-mono text-sm text-white uppercase placeholder:normal-case"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoComplete="off"
                placeholder="ABCD-1234"
              />
            </div>
            <details className="rounded-xl border border-white/10 bg-black/20 p-4">
              <summary className="cursor-pointer text-sm font-medium text-white">PIN or support details</summary>
              <div className="mt-4 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="redeem-pin" className="text-white/85">
                    PIN <span className="text-white/45">(if your voucher has one)</span>
                  </Label>
                  <Input
                    id="redeem-pin"
                    className="min-h-11 border-white/20 bg-black/30 text-white"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="redeem-customer" className="text-white/85">
                    Customer ID <span className="text-white/45">(only if staff gave you one)</span>
                  </Label>
                  <Input
                    id="redeem-customer"
                    className="min-h-11 border-white/20 bg-black/30 font-mono text-xs text-white"
                    value={customerId}
                    onChange={(e) => setCustomerId(e.target.value)}
                    autoComplete="off"
                  />
                </div>
              </div>
            </details>
            <Button
              type="submit"
              className="min-h-12 w-full font-semibold text-slate-900"
              style={{ backgroundColor: "var(--portal-accent)" }}
              disabled={busy}
            >
              {busy ? "Applying…" : "Apply voucher"}
            </Button>
          </form>
        </CardContent>
      </Card>
      {result != null && (
        <Card className="border-white/10 bg-black/30 text-white">
          <CardHeader>
            <CardTitle className="text-base font-display">Voucher result</CardTitle>
          </CardHeader>
          <CardContent>
            {authorization?.available && authorization.login_url && authorization.username && authorization.password && (
              <div className="mb-4 rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-4">
                <p className="text-sm font-medium text-white">Voucher access is ready for this device.</p>
                <Button
                  type="button"
                  className="mt-3 min-h-11 text-slate-900"
                  style={{ backgroundColor: "var(--portal-accent)" }}
                  onClick={() => submitHotspotLogin(authorization)}
                >
                  Connect this device
                </Button>
              </div>
            )}
            {!authorization?.available && (
              <p className="text-sm text-white/75">If internet does not start right away, open <strong>Access</strong> on this same phone.</p>
            )}
            <details className="mt-4 rounded-xl border border-white/10 bg-black/25 p-4">
              <summary className="cursor-pointer text-sm font-medium text-white">Support details</summary>
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-black/40 p-3 text-xs">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
