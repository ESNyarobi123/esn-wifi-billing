"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, CheckCircle2, LifeBuoy, MoreHorizontal, Ticket, Wifi } from "lucide-react";
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
  const pathname = usePathname();
  const base = `/${siteSlug}`;
  const primaryLinks = [
    { href: base, label: "Plans", icon: Wifi, active: pathname === base || pathname === `${base}/plans` || pathname === `${base}/pay` },
    { href: `${base}/redeem`, label: "Voucher", icon: Ticket, active: pathname === `${base}/redeem` },
  ];
  const supportLinks = [
    { href: `${base}/access`, label: "Check access", icon: CheckCircle2 },
    { href: `${base}/session`, label: "Session status", icon: LifeBuoy },
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
        <div className="mx-auto flex max-w-lg flex-col gap-3 px-4 py-3 sm:max-w-2xl sm:py-4">
          <div className="flex items-center justify-between gap-3">
            <Link
              href={base}
              className="flex min-w-0 items-center gap-3 rounded-lg outline-none ring-[var(--portal-accent)] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118]"
            >
              <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl font-display text-sm font-bold text-slate-900 shadow-md sm:h-12 sm:w-12"
                style={{ backgroundColor: accent }}
              >
                <Wifi className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden />
              </div>
              <div className="min-w-0 text-left">
                <p className="truncate font-display text-base font-semibold leading-tight sm:text-lg">{siteName}</p>
                <p className="text-[10px] uppercase tracking-widest text-white/50">Guest Wi‑Fi</p>
              </div>
            </Link>
            <details className="group relative">
              <summary className="flex min-h-10 list-none items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 text-xs font-medium text-white/90 outline-none transition hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] [&::-webkit-details-marker]:hidden">
                <MoreHorizontal className="h-4 w-4" aria-hidden />
                More
              </summary>
              <div className="absolute right-0 mt-2 w-52 overflow-hidden rounded-2xl border border-white/10 bg-[#172016] p-2 shadow-2xl ring-1 ring-black/20">
                {supportLinks.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm text-white/85 transition hover:bg-white/10 hover:text-white"
                    >
                      <Icon className="h-4 w-4 text-[var(--portal-accent)]" aria-hidden />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </details>
          </div>
          {welcome && <p className="text-center text-sm leading-relaxed text-white/75 sm:text-left">{welcome}</p>}
          <nav className="grid grid-cols-2 gap-2" aria-label="Portal navigation">
            {primaryLinks.map((l, i) => {
              const Icon = l.icon;
              return (
              <motion.div
                key={l.href}
                initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={reduceMotion ? {} : { delay: i * 0.03 }}
              >
                <Link
                  href={l.href}
                  className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a2118] ${
                    l.active
                      ? "border-[var(--portal-accent)] bg-[var(--portal-accent)] text-slate-950"
                      : "border-white/15 bg-white/5 text-white/95 hover:border-[var(--portal-accent)] hover:bg-white/10"
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                  {l.label}
                </Link>
              </motion.div>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-lg px-4 py-6 sm:max-w-2xl sm:py-10">{children}</main>
    </div>
  );
}
