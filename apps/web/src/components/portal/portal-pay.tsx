"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
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
import { hotspotContextToPayload, submitHotspotLogin } from "@/lib/portal/router-auth";
import type { PortalAuthorization } from "@/lib/portal/router-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PortalInlineError } from "@/components/portal/portal-inline-error";
import { formatMoney } from "@/lib/format";

type PortalPaymentRefresh = {
  payment_id: string;
  order_reference: string;
  gateway_status: string | null;
  normalized_outcome: string;
  payment_status: string;
  activation?: {
    activated?: boolean;
    grant_id?: string | null;
    authorization?: {
      available: boolean;
      login_url?: string | null;
      username?: string | null;
      password?: string | null;
      router_name?: string | null;
      rate_limit?: string | null;
      reason?: string | null;
    } | null;
  } | null;
};

function toPortalAuthorization(
  auth: NonNullable<NonNullable<PortalPaymentRefresh["activation"]>["authorization"]>,
): PortalAuthorization {
  return {
    available: auth.available,
    login_url: auth.login_url ?? undefined,
    username: auth.username ?? undefined,
    password: auth.password ?? undefined,
    router_name: auth.router_name ?? undefined,
    rate_limit: auth.rate_limit ?? undefined,
    reason: auth.reason ?? undefined,
  };
}

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
    customer_id?: string | null;
    resolved_by?: string | null;
    payment?: Record<string, unknown>;
    checkout?: Record<string, unknown>;
    provider?: Record<string, unknown>;
  } | null>(null);
  const [paymentRefresh, setPaymentRefresh] = useState<PortalPaymentRefresh | null>(null);
  const [paymentRefreshNote, setPaymentRefreshNote] = useState<string | null>(null);
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
    setPaymentRefresh(null);
    setPaymentRefreshNote(null);
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
        customer_id?: string | null;
        resolved_by?: string | null;
        checkout: Record<string, unknown>;
        payment?: Record<string, unknown>;
        provider?: Record<string, unknown>;
      }>(`/portal/${siteSlug}/pay`, body);
      if (res.customer_id) {
        setStoredCustomerId(siteSlug, res.customer_id);
        setCustomerId(res.customer_id);
      } else if (customerId.trim()) {
        setStoredCustomerId(siteSlug, customerId.trim());
      }
      setStoredPortalPhone(siteSlug, phone.trim());
      setCheckout(res);
      toast.success("Payment started. Confirm the prompt on your phone to continue.");
    } catch (err) {
      toast.error(userFacingApiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!checkout?.payment_id) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempts = 0;
    let successHandled = false;

    const pollStatus = async () => {
      attempts += 1;
      try {
        const result = await apiPostPublic<PortalPaymentRefresh>(`/portal/${siteSlug}/payments/${checkout.payment_id}/refresh-status`);
        if (cancelled) return;
        setPaymentRefresh(result);
        setPaymentRefreshNote(null);

        if (result.payment_status === "success") {
          successHandled = true;
          const authorization = result.activation?.authorization;
          toast.success("Payment confirmed. Finishing your Wi-Fi access now.");
          if (authorization?.available && authorization.login_url && authorization.username && authorization.password) {
            timer = setTimeout(() => submitHotspotLogin(toPortalAuthorization(authorization)), 600);
            return;
          }
          return;
        }

        if (result.payment_status === "failed" || result.normalized_outcome === "failure") {
          successHandled = true;
          setPaymentRefreshNote("Payment was not confirmed. Please try again or ask for support.");
          toast.error("Payment was not confirmed.");
          return;
        }
      } catch (error) {
        if (cancelled) return;
        if (attempts >= 18) {
          setPaymentRefreshNote(userFacingApiMessage(error));
        }
      }

      if (attempts >= 18 || successHandled) {
        if (!successHandled && !paymentRefreshNote) {
          setPaymentRefreshNote("Still waiting for ClickPesa confirmation. Keep this page open for a little longer, or open Access to retry.");
        }
        return;
      }
      timer = setTimeout(pollStatus, 5000);
    };

    timer = setTimeout(pollStatus, 4000);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [checkout?.payment_id, siteSlug]);

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
      <div className="text-center sm:text-left">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-white/45">Quick checkout</p>
        <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">Enter phone number</h1>
        <p className="mt-2 text-pretty text-sm text-white/70">
          We will send a payment prompt, then connect this device automatically.
        </p>
      </div>
      {detectedMac && (
        <div className="rounded-2xl border border-[var(--portal-accent)]/20 bg-[var(--portal-accent)]/10 p-3 text-center text-xs text-white/75 sm:text-left">
          This phone was detected from the hotspot. No customer ID is needed.
        </div>
      )}
      {!checkout && (
        <Card className="overflow-hidden border-white/10 bg-white/[0.07] text-white shadow-[0_22px_70px_rgba(0,0,0,0.22)]">
          <CardContent className="p-5 sm:p-6">
            <form className="space-y-5" onSubmit={pay} noValidate>
              {showPlanSelect ? (
                <div className="space-y-2">
                  <Label htmlFor="portal-plan" className="text-white/85">
                    Plan <span className="text-rose-300">*</span>
                  </Label>
                  <select
                    id="portal-plan"
                    className="flex min-h-12 w-full rounded-2xl border border-white/15 bg-black/25 px-4 py-2 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]"
                    value={planId}
                    onChange={(e) => setPlanId(e.target.value)}
                    required
                    aria-required="true"
                  >
                    <option value="">Select a plan...</option>
                    {plansQ.data?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} - {formatMoney(p.price_amount, p.currency)}
                      </option>
                    ))}
                  </select>
                </div>
              ) : selected ? (
                <div className="rounded-3xl border border-[var(--portal-accent)]/25 bg-black/20 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-white/40">Selected plan</p>
                  <div className="mt-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-display text-xl font-bold text-white">{selected.name}</p>
                      {selected.description && <p className="mt-1 text-sm text-white/58">{selected.description}</p>}
                    </div>
                    <div className="text-right">
                      <p className="font-display text-2xl font-bold text-[var(--portal-accent)]">
                        {formatMoney(selected.price_amount, selected.currency).replace("TZS", "").trim()}
                      </p>
                      <p className="text-xs font-semibold uppercase tracking-widest text-white/45">{selected.currency}</p>
                    </div>
                  </div>
                </div>
              ) : null}
              <div className="space-y-2">
                <Label htmlFor="portal-phone" className="text-white/85">
                  Phone number <span className="text-rose-300">*</span>
                </Label>
                <Input
                  id="portal-phone"
                  className="min-h-12 rounded-2xl border-white/15 bg-black/25 px-4 text-white"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  autoComplete="tel"
                  inputMode="tel"
                  placeholder="07XXXXXXXX"
                  required
                />
                <p className="text-xs text-white/50">The payment prompt will be sent to this number.</p>
              </div>
              <details className="rounded-2xl border border-white/10 bg-black/15 p-4">
                <summary className="cursor-pointer text-sm font-medium text-white/85">More options</summary>
                <div className="mt-4 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="portal-customer-id" className="text-white/85">
                    Customer ID <span className="text-white/50">(only if staff gave you one)</span>
                  </Label>
                  <Input
                    id="portal-customer-id"
                    className="min-h-11 border-white/15 bg-black/25 font-mono text-xs text-white placeholder:text-white/40"
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
                      className="min-h-11 border-white/15 bg-black/25 text-white"
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
                      className="min-h-11 border-white/15 bg-black/25 text-white"
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
                className="min-h-[3.25rem] w-full rounded-2xl text-base font-bold text-slate-950"
                style={{ backgroundColor: "var(--portal-accent)" }}
                disabled={busy || plansQ.isLoading}
              >
                {busy ? "Sending prompt..." : "Pay now"}
              </Button>
              <Button asChild variant="ghost" className="min-h-11 w-full rounded-2xl text-white/75 hover:bg-white/10 hover:text-white">
                <Link href={`/${siteSlug}`}>Back to plans</Link>
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {checkout && (
        <Card className="border-white/10 bg-white/[0.07] text-white shadow-[0_22px_70px_rgba(0,0,0,0.22)]">
          <CardHeader>
            <CardTitle className="font-display text-xl">Payment in progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-4">
              <p className="text-sm font-medium text-white">Check your phone and approve the payment prompt.</p>
              {checkout.order_reference && (
                <p className="mt-2 text-xs text-white/75">
                  Order reference: <span className="font-mono text-white">{checkout.order_reference}</span>
                </p>
              )}
              {checkout.resolved_by && (
                <p className="mt-2 text-xs text-white/60">Customer resolution: {checkout.resolved_by}</p>
              )}
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/80">
              <p className="font-medium text-white">Live status</p>
              <p className="mt-2">
                {paymentRefresh?.payment_status === "success"
                  ? "Payment confirmed. We’re finishing hotspot access for this device."
                  : paymentRefresh?.payment_status === "failed"
                    ? "Payment failed or was reversed."
                    : "Waiting for provider confirmation from ClickPesa…"}
              </p>
              {paymentRefresh?.gateway_status && (
                <p className="mt-2 text-xs text-white/60">
                  Provider status: <span className="font-mono text-white">{paymentRefresh.gateway_status}</span>
                </p>
              )}
              {paymentRefresh?.activation?.authorization?.available &&
                paymentRefresh.activation.authorization.login_url &&
                paymentRefresh.activation.authorization.username &&
                paymentRefresh.activation.authorization.password && (
                  <Button
                    type="button"
                    className="mt-3 min-h-11 text-slate-900"
                    style={{ backgroundColor: "var(--portal-accent)" }}
                    onClick={() => submitHotspotLogin(toPortalAuthorization(paymentRefresh.activation!.authorization!))}
                  >
                    Connect this device
                  </Button>
                )}
              {paymentRefreshNote && (
                <div className="mt-3 rounded-lg border border-amber-400/20 bg-amber-500/10 p-3 text-xs text-white/80">
                  {paymentRefreshNote}{" "}
                  <Link href={`/${siteSlug}/access`} className="underline underline-offset-2">
                    Open Access
                  </Link>
                </div>
              )}
            </div>
            <details className="rounded-xl border border-white/10 bg-black/25 p-4">
              <summary className="cursor-pointer text-sm font-medium text-white">Support details</summary>
              <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-black/40 p-3 text-xs">
                {JSON.stringify(
                  {
                    initiated: checkout.checkout ?? checkout.provider ?? checkout,
                    latest_status: paymentRefresh,
                  },
                  null,
                  2,
                )}
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
