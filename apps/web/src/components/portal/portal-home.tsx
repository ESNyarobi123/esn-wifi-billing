"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PortalCustomerBanner } from "@/components/portal/portal-customer-banner";
import { PortalInlineError } from "@/components/portal/portal-inline-error";
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

  const base = `/${siteSlug}`;

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

      <div className="grid gap-3 sm:grid-cols-2">
        <Button
          asChild
          className="min-h-[3.25rem] w-full flex-col gap-1 py-6 text-base font-semibold shadow-lg sm:min-h-[3.5rem]"
          style={{ backgroundColor: "var(--portal-accent)", color: "#141816" }}
        >
          <Link href={`${base}/plans`}>
            View plans
            <span className="text-xs font-normal opacity-85">Compare prices &amp; speeds</span>
          </Link>
        </Button>
        <Button
          asChild
          variant="outline"
          className="min-h-[3.25rem] w-full flex-col gap-1 border-white/25 bg-white/5 py-6 text-base text-white hover:bg-white/10 sm:min-h-[3.5rem]"
        >
          <Link href={`${base}/redeem`}>
            Redeem voucher
            <span className="text-xs font-normal text-white/65">Needs customer ID</span>
          </Link>
        </Button>
      </div>

      <div className="flex justify-center pt-2">
        <Button variant="ghost" className="min-h-11 gap-2 text-[var(--portal-accent)] hover:bg-white/5 hover:text-white" asChild>
          <Link href={`${base}/pay`}>
            Pay for access <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
          </Link>
        </Button>
      </div>
    </div>
  );
}
