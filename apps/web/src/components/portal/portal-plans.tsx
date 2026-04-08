"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ApiRequestError, apiGetPublic } from "@/lib/api/client";
import type { PortalPlan } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { isRateLimitedError, userFacingApiMessage } from "@/lib/api/error-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Choose a plan</h1>
        <p className="mt-2 max-w-xl text-pretty text-sm text-white/75">Tap any plan, enter your phone number, and pay.</p>
      </div>
      {q.isLoading && (
        <div className="space-y-3" aria-busy="true" aria-label="Loading plans">
          <span className="sr-only">Loading plans…</span>
          <Skeleton className="h-24 rounded-xl bg-white/10" />
          <Skeleton className="h-24 rounded-xl bg-white/10" />
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
            <Card className="border-white/10 bg-white/5 text-white transition-colors hover:border-[var(--portal-accent)]/40">
              <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-display text-lg font-semibold">{p.name}</p>
                    <Badge variant="outline" className="border-white/25 text-white/90" aria-label={`Plan type: ${p.plan_type}`}>
                      {p.plan_type}
                    </Badge>
                  </div>
                  {p.description && (
                    <p className="mt-1 text-pretty text-sm leading-relaxed text-white/70">{p.description}</p>
                  )}
                  <p className="mt-3 text-xl font-semibold" style={{ color: "var(--portal-accent)" }}>
                    <span className="sr-only">Price: </span>
                    {formatMoney(p.price_amount, p.currency)}
                  </p>
                </div>
                <Button
                  asChild
                  className="min-h-12 w-full shrink-0 font-semibold text-slate-900 sm:w-auto sm:min-w-[8rem]"
                  style={{ backgroundColor: "var(--portal-accent)" }}
                >
                  <Link href={`${base}/pay?plan=${p.id}`}>Pay with this plan</Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
      {!q.isLoading && !q.data?.length && (
        <p className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-white/70" role="status">
          No plans are available here yet. Ask staff or try again later.
        </p>
      )}
      {embedded && (
        <Button
          asChild
          variant="outline"
          className="min-h-[3.25rem] w-full flex-col gap-1 border-white/25 bg-white/5 py-6 text-base text-white hover:bg-white/10 sm:min-h-[3.5rem]"
        >
          <Link href={`${base}/redeem`}>
            Redeem voucher
            <span className="text-xs font-normal text-white/65">Use this if you already have a voucher code</span>
          </Link>
        </Button>
      )}
    </div>
  );
}
