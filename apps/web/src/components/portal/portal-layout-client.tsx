"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, Wifi } from "lucide-react";
import { captureHotspotContext } from "@/lib/portal/hotspot-context";
import type { PortalSiteHealth } from "@/lib/portal/site-health";

export function PortalLayoutClient({
  siteSlug,
  siteName,
  accent,
  welcome,
  siteHealth = "ok",
  children,
}: {
  siteSlug: string;
  siteName: string;
  accent: string;
  welcome: string | null;
  siteHealth?: PortalSiteHealth;
  children: ReactNode;
}) {
  const reduceMotion = useReducedMotion();
  const search = useSearchParams();
  const base = `/${siteSlug}`;
  const links = [
    { href: base, label: "Home" },
    { href: `${base}/plans`, label: "Plans" },
    { href: `${base}/pay`, label: "Pay" },
    { href: `${base}/redeem`, label: "Voucher" },
    { href: `${base}/access`, label: "Access" },
    { href: `${base}/session`, label: "Session" },
  ];

  useEffect(() => {
    captureHotspotContext(siteSlug, search);
  }, [search, siteSlug]);

  return (
    <div
      className="min-h-screen text-white"
      style={{
        background: `linear-gradient(165deg, #313B2F 0%, #1a2118 45%, #0f140e 100%)`,
        ["--portal-accent" as string]: accent,
      }}
    >
      {siteHealth === "missing" && (
        <div
          className="border-b border-amber-400/30 bg-amber-500/15 px-4 py-3 text-center text-sm text-amber-50 sm:text-left"
          role="status"
        >
          <strong className="font-semibold">Site not found.</strong>{" "}
          <span className="opacity-90">
            This portal link may be wrong or the location is not active. Ask staff for the correct Wi‑Fi sign-in page.
          </span>
        </div>
      )}
      {siteHealth === "degraded" && (
        <div
          className="flex items-start gap-2 border-b border-white/10 bg-black/25 px-4 py-3 text-sm text-white/90"
          role="status"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--portal-accent)]" aria-hidden />
          <span className="text-pretty">
            We couldn&apos;t load the latest branding from the server. You can still browse plans and pay — if something
            fails, confirm Wi‑Fi with staff or try again shortly.
          </span>
        </div>
      )}
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/25 backdrop-blur-md">
        <div className="mx-auto flex max-w-lg flex-col gap-3 px-4 py-4 sm:max-w-2xl sm:py-5">
          <div className="flex items-center justify-between gap-3">
            <Link
              href={base}
              className="flex min-w-0 items-center gap-3 rounded-lg outline-none ring-[var(--portal-accent)] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]"
            >
              <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl font-display text-sm font-bold text-slate-900 shadow-md sm:h-12 sm:w-12"
                style={{ backgroundColor: accent }}
              >
                <Wifi className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden />
              </div>
              <div className="min-w-0 text-left">
                <p className="truncate font-display text-base font-semibold leading-tight sm:text-lg">{siteName}</p>
                <p className="text-[10px] uppercase tracking-widest text-white/50">Guest Wi‑Fi</p>
              </div>
            </Link>
          </div>
          {welcome && <p className="text-center text-sm leading-relaxed text-white/85 sm:text-left">{welcome}</p>}
          <nav className="flex flex-wrap gap-2" aria-label="Portal navigation">
            {links.map((l, i) => (
              <motion.div
                key={l.href}
                initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={reduceMotion ? {} : { delay: i * 0.03 }}
              >
                <Link
                  href={l.href}
                  className="inline-flex min-h-11 items-center justify-center rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-medium text-white/95 outline-none transition-colors hover:border-[var(--portal-accent)] hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118] sm:min-h-10 sm:px-3 sm:py-1.5"
                >
                  {l.label}
                </Link>
              </motion.div>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-lg px-4 py-6 sm:max-w-2xl sm:py-10">{children}</main>
    </div>
  );
}
