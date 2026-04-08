"use client";

import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { Radio } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { PortalInlineError } from "@/components/portal/portal-inline-error";
import { PortalPlans } from "@/components/portal/portal-plans";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGetPublic, ApiRequestError } from "@/lib/api/client";
import { isRateLimitedError, userFacingApiMessage } from "@/lib/api/error-utils";

type Status = {
  site: { name: string; slug: string; timezone: string };
  routers: { total: number; online: number };
};

export function PortalHome({ siteSlug }: { siteSlug: string }) {
  const reduceMotion = useReducedMotion();
  const q = useQuery({
    queryKey: ["portal-status", siteSlug],
    queryFn: () => apiGetPublic<Status>(`/portal/${siteSlug}/status`),
    retry: (n, err) => {
      if (err instanceof ApiRequestError && err.status === 429) return false;
      return n < 2;
    },
  });

  if (q.error) {
    const err = q.error as Error;
    return (
      <PortalInlineError
        title={isRateLimitedError(err) ? "Please wait a moment" : "We couldn’t load the network status"}
        description={userFacingApiMessage(err)}
        variant={isRateLimitedError(err) ? "rate_limit" : "generic"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PortalCustomerBanner siteSlug={siteSlug} />

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-3 text-center sm:text-left"
      >
        <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Get online in a few taps</h1>
        <p className="text-pretty text-sm leading-relaxed text-white/75 sm:text-base">
          Pick a plan, pay securely, or redeem a voucher. Check <span className="text-white">Access</span> anytime to see
          if you&apos;re good to browse.
        </p>
      </motion.div>

      {q.isLoading && (
        <Skeleton className="h-28 w-full rounded-xl bg-white/10" aria-hidden />
      )}
      {q.data && (
        <Card className="border-white/10 bg-white/5 text-white shadow-lg backdrop-blur">
          <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--portal-accent)]/20 text-[var(--portal-accent)]"
                aria-hidden
              >
                <Radio className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm text-white/60">Venue equipment</p>
                <p className="font-display text-lg font-semibold">
                  <span className="sr-only">Routers online: </span>
                  {q.data.routers.online} of {q.data.routers.total} online
                </p>
              </div>
            </div>
            <p className="text-xs text-white/50">{q.data.site.timezone}</p>
          </CardContent>
        </Card>
      )}

      <PortalPlans siteSlug={siteSlug} embedded />
    </div>
  );
}
