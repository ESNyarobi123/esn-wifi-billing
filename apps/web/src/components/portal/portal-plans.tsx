"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ApiRequestError, apiGetPublic } from "@/lib/api/client";
import type { PortalPlan } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { isRateLimitedError, userFacingApiMessage } from "@/lib/api/error-utils";
import { Card, CardContent } from "@/components/ui/card";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { PortalInlineError } from "@/components/portal/portal-inline-error";
import { Skeleton } from "@/components/ui/skeleton";

export function PortalPlans({
  siteSlug,
  embedded = false,
}: {
  siteSlug: string;
  embedded?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const q = useQuery({
    queryKey: ["portal-plans", siteSlug],
    queryFn: () => apiGetPublic<PortalPlan[]>(`/portal/${siteSlug}/plans`),
    retry: (n, err) => !(err instanceof ApiRequestError && err.status === 429) && n < 2,
  });

  const base = `/${siteSlug}`;

  if (q.error) {
    const err = q.error as Error;
    return (
      <PortalInlineError
        title={isRateLimitedError(err) ? "Please wait a moment" : "Plans couldn’t load"}
        description={userFacingApiMessage(err)}
        variant={isRateLimitedError(err) ? "rate_limit" : "generic"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {!embedded && <PortalCustomerBanner siteSlug={siteSlug} />}
      {!embedded && (
        <div className="text-center sm:text-left">
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Choose a plan</h1>
          <p className="mt-2 max-w-xl text-pretty text-sm text-white/75">Tap a package, enter your phone number, and pay.</p>
        </div>
      )}
      {q.isLoading && (
        <div className="space-y-3" aria-busy="true" aria-label="Loading plans">
          <span className="sr-only">Loading plans…</span>
          <Skeleton className="h-28 rounded-3xl bg-white/10" />
          <Skeleton className="h-28 rounded-3xl bg-white/10" />
        </div>
      )}
      <div className="space-y-3">
        {q.data?.map((p, i) => (
          <motion.div
            key={p.id}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={reduceMotion ? {} : { delay: Math.min(i * 0.04, 0.2) }}
          >
            <Link href={`${base}/pay?plan=${p.id}`} className="block rounded-3xl outline-none focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]">
              <Card className="group border-white/10 bg-white/[0.07] text-white shadow-[0_18px_60px_rgba(0,0,0,0.18)] transition duration-200 hover:-translate-y-0.5 hover:border-[var(--portal-accent)]/50 hover:bg-white/[0.1]">
                <CardContent className="grid grid-cols-[1fr_auto] items-center gap-4 p-5 sm:p-6">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-display text-xl font-bold leading-tight">{p.name}</p>
                      <span className="rounded-full border border-white/15 bg-black/20 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/70">
                        {p.plan_type}
                      </span>
                    </div>
                    {p.description && (
                      <p className="mt-2 text-pretty text-sm leading-relaxed text-white/60">{p.description}</p>
                    )}
                    <p className="mt-3 text-xs font-medium text-white/45">Tap to continue</p>
                  </div>
                  <div className="text-right">
                    <p className="font-display text-2xl font-bold leading-none text-[var(--portal-accent)] sm:text-3xl">
                      <span className="sr-only">Price: </span>
                      {formatMoney(p.price_amount, p.currency).replace("TZS", "").trim()}
                    </p>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-white/50">{p.currency}</p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>
      {!q.isLoading && !q.data?.length && (
        <p className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/70" role="status">
          No plans are available here yet. Ask staff or try again later.
        </p>
      )}
      {embedded && (
        <Link
          href={`${base}/redeem`}
          className="flex min-h-[3.25rem] w-full flex-col items-center justify-center gap-1 rounded-2xl border border-white/20 bg-white/5 px-4 py-5 text-center text-base font-semibold text-white outline-none transition hover:border-[var(--portal-accent)]/60 hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]"
        >
          Redeem voucher
          <span className="text-xs font-normal text-white/60">Use this if you already have a voucher code</span>
        </Link>
      )}
    </div>
  );
}
