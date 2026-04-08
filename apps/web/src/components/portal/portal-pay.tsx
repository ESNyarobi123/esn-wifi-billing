"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import { ApiRequestError, apiGetPublic, apiPostPublic } from "@/lib/api/client";
import { isRateLimitedError, userFacingApiMessage } from "@/lib/api/error-utils";
import type { PortalPlan } from "@/lib/api/types";
import {
  getStoredCustomerId,
  getStoredPortalPhone,
  setStoredCustomerId,
  setStoredPortalPhone,
} from "@/lib/portal/customer-storage";
import { getStoredHotspotContext } from "@/lib/portal/hotspot-context";
import { hotspotContextToPayload } from "@/lib/portal/router-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { PortalInlineError } from "@/components/portal/portal-inline-error";
import { formatMoney } from "@/lib/format";

function PortalPayInner({ siteSlug }: { siteSlug: string }) {
  const search = useSearchParams();
  const planPref = search.get("plan") ?? "";

  const plansQ = useQuery({
    queryKey: ["portal-plans", siteSlug],
    queryFn: () => apiGetPublic<PortalPlan[]>(`/portal/${siteSlug}/plans`),
    retry: (n, err) => !(err instanceof ApiRequestError && err.status === 429) && n < 2,
  });

  const [planId, setPlanId] = useState(planPref);
  const [customerId, setCustomerId] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkout, setCheckout] = useState<{
    payment_id?: string;
    order_reference?: string;
    payment?: Record<string, unknown>;
    checkout?: Record<string, unknown>;
    provider?: Record<string, unknown>;
  } | null>(null);
  const [detectedMac, setDetectedMac] = useState<string | null>(null);

  useEffect(() => {
    const sid = getStoredCustomerId(siteSlug);
    if (sid) setCustomerId(sid);
    const storedPhone = getStoredPortalPhone(siteSlug);
    if (storedPhone) setPhone(storedPhone);
    const context = getStoredHotspotContext(siteSlug);
    if (context?.mac_address) setDetectedMac(context.mac_address);
  }, [siteSlug]);

  useEffect(() => {
    if (planPref) setPlanId(planPref);
  }, [planPref]);

  useEffect(() => {
    if (planPref || planId || !plansQ.data?.length) return;
    if (plansQ.data.length === 1) {
      setPlanId(plansQ.data[0].id);
    }
  }, [planId, planPref, plansQ.data]);

  const selected = plansQ.data?.find((p) => p.id === planId);
  const showPlanSelect = !planPref && (plansQ.data?.length ?? 0) > 1;

  async function pay(e: React.FormEvent) {
    e.preventDefault();
    if (!planId || !selected) {
      toast.error("Select a plan");
      return;
    }
    if (!phone.trim()) {
      toast.error("Enter the phone number that will receive the payment prompt.");
      return;
    }
    setBusy(true);
    setCheckout(null);
    try {
      const hotspotContext = hotspotContextToPayload(getStoredHotspotContext(siteSlug));
      const body = {
        plan_id: planId,
        amount: selected.price_amount,
        currency: selected.currency,
        customer_id: customerId.trim() || null,
        email: email.trim() || null,
        phone: phone.trim(),
        full_name: fullName.trim() || null,
        hotspot_context: hotspotContext,
      };
      const res = await apiPostPublic<{
        payment_id: string;
        order_reference: string;
        checkout: Record<string, unknown>;
        payment?: Record<string, unknown>;
        provider?: Record<string, unknown>;
      }>(`/portal/${siteSlug}/pay`, body);
      if (customerId.trim()) setStoredCustomerId(siteSlug, customerId.trim());
      setStoredPortalPhone(siteSlug, phone.trim());
      setCheckout(res);
      toast.success("Payment started. Confirm the prompt on your phone to continue.");
    } catch (err) {
      toast.error(userFacingApiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (plansQ.error) {
    const err = plansQ.error as Error;
    return (
      <PortalInlineError
        title={isRateLimitedError(err) ? "Please wait a moment" : "Checkout couldn’t load plans"}
        description={userFacingApiMessage(err)}
        variant={isRateLimitedError(err) ? "rate_limit" : "generic"}
        onRetry={() => void plansQ.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PortalCustomerBanner siteSlug={siteSlug} />
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Pay for access</h1>
        <p className="mt-2 text-pretty text-sm text-white/75">
          Keep it simple: choose a plan, enter the phone number that will receive the payment prompt, then confirm payment.
        </p>
      </div>
      {detectedMac && (
        <div className="rounded-xl border border-[var(--portal-accent)]/30 bg-black/25 p-3 text-sm text-white/85">
          This device was detected automatically. Your hotspot details will be linked in the background.
        </div>
      )}
      <Card className="border-white/10 bg-white/5 text-white">
        <CardHeader>
          <CardTitle className="text-base font-display">Quick checkout</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={pay} noValidate>
            {showPlanSelect ? (
              <div className="space-y-2">
                <Label htmlFor="portal-plan" className="text-white/85">
                  Plan <span className="text-rose-300">*</span>
                </Label>
                <select
                  id="portal-plan"
                  className="flex min-h-11 w-full rounded-md border border-white/20 bg-black/30 px-3 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]"
                  value={planId}
                  onChange={(e) => setPlanId(e.target.value)}
                  required
                  aria-required="true"
                >
                  <option value="">Select a plan…</option>
                  {plansQ.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} — {formatMoney(p.price_amount, p.currency)}
                    </option>
                  ))}
                </select>
              </div>
            ) : selected ? (
              <div className="rounded-xl border border-[var(--portal-accent)]/25 bg-black/25 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-white/45">Selected plan</p>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <div>
                    <p className="font-display text-lg font-semibold text-white">{selected.name}</p>
                    {selected.description && <p className="mt-1 text-sm text-white/65">{selected.description}</p>}
                  </div>
                  <p className="text-lg font-semibold" style={{ color: "var(--portal-accent)" }}>
                    {formatMoney(selected.price_amount, selected.currency)}
                  </p>
                </div>
              </div>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="portal-phone" className="text-white/85">
                Phone number <span className="text-rose-300">*</span>
              </Label>
              <Input
                id="portal-phone"
                className="min-h-11 border-white/20 bg-black/30 text-white"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                autoComplete="tel"
                inputMode="tel"
                placeholder="07XXXXXXXX or 2557XXXXXXXX"
                required
              />
              <p className="text-xs text-white/55">We&apos;ll use this number for the payment prompt.</p>
            </div>
            <details className="rounded-xl border border-white/10 bg-black/20 p-4">
              <summary className="cursor-pointer text-sm font-medium text-white">More options</summary>
              <div className="mt-4 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="portal-customer-id" className="text-white/85">
                    Customer ID <span className="text-white/50">(only if staff gave you one)</span>
                  </Label>
                  <Input
                    id="portal-customer-id"
                    className="min-h-11 border-white/20 bg-black/30 font-mono text-xs text-white placeholder:text-white/40"
                    value={customerId}
                    onChange={(e) => setCustomerId(e.target.value)}
                    placeholder="Optional"
                    autoComplete="off"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="portal-full-name" className="text-white/85">
                      Full name
                    </Label>
                    <Input
                      id="portal-full-name"
                      className="min-h-11 border-white/20 bg-black/30 text-white"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      autoComplete="name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="portal-email" className="text-white/85">
                      Email
                    </Label>
                    <Input
                      id="portal-email"
                      className="min-h-11 border-white/20 bg-black/30 text-white"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                    />
                  </div>
                </div>
              </div>
            </details>
            <Button
              type="submit"
              className="min-h-12 w-full font-semibold text-slate-900"
              style={{ backgroundColor: "var(--portal-accent)" }}
              disabled={busy || plansQ.isLoading}
            >
              {busy ? "Starting…" : "Pay now"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {checkout && (
        <Card className="border-white/10 bg-black/30 text-white">
          <CardHeader>
            <CardTitle className="text-base">Payment started</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-4">
              <p className="text-sm font-medium text-white">Check your phone and approve the payment prompt.</p>
              {checkout.order_reference && (
                <p className="mt-2 text-xs text-white/75">
                  Order reference: <span className="font-mono text-white">{checkout.order_reference}</span>
                </p>
              )}
            </div>
            <p className="mt-3 text-sm text-white/75">
              After payment succeeds, open <strong>Access</strong> on this same device to finish connecting this hotspot automatically.
            </p>
            <details className="rounded-xl border border-white/10 bg-black/25 p-4">
              <summary className="cursor-pointer text-sm font-medium text-white">Support details</summary>
              <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-black/40 p-3 text-xs">
                {JSON.stringify(checkout.checkout ?? checkout.provider ?? checkout, null, 2)}
              </pre>
            </details>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function PortalPay({ siteSlug }: { siteSlug: string }) {
  return (
    <Suspense
      fallback={
        <div className="rounded-xl border border-white/10 bg-white/5 p-6 text-sm text-white/60" role="status">
          Loading checkout…
        </div>
      }
    >
      <PortalPayInner siteSlug={siteSlug} />
    </Suspense>
  );
}
