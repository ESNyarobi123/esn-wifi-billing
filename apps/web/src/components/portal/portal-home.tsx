"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Wifi } from "lucide-react";
import { PortalPlans } from "@/components/portal/portal-plans";

export function PortalHome({ siteSlug }: { siteSlug: string }) {
  const reduceMotion = useReducedMotion();

  return (
    <div className="space-y-8">
      <motion.section
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-md text-center"
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-[var(--portal-accent)] text-slate-950 shadow-[0_18px_50px_rgba(0,0,0,0.28)]">
          <Wifi className="h-8 w-8" aria-hidden />
        </div>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.32em] text-white/45">Secure Wi‑Fi billing</p>
        <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">Choose your plan</h1>
        <p className="mt-2 text-sm leading-relaxed text-white/65 sm:text-base">
          Select a package, enter your phone number, confirm payment, and connect automatically.
        </p>
      </motion.section>

      <PortalPlans siteSlug={siteSlug} embedded />
    </div>
  );
}
