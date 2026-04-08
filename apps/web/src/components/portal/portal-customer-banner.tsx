"use client";

import { useEffect, useState } from "react";
import { clearStoredCustomerId, getStoredCustomerId } from "@/lib/portal/customer-storage";
import { getStoredHotspotContext } from "@/lib/portal/hotspot-context";

export function PortalCustomerBanner({ siteSlug }: { siteSlug: string }) {
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [detectedMac, setDetectedMac] = useState<string | null>(null);

  useEffect(() => {
    setCustomerId(getStoredCustomerId(siteSlug));
    setDetectedMac(getStoredHotspotContext(siteSlug)?.mac_address ?? null);
  }, [siteSlug]);

  if (!customerId) {
    return (
      <div
        className="rounded-xl border border-white/15 bg-white/5 p-4 text-sm leading-relaxed text-white/85"
        role="note"
      >
        <p className="font-medium text-white">Quick sign-in</p>
        <p className="mt-1 text-pretty text-white/75">
          {detectedMac
            ? "This device was detected automatically. Most people only need to choose a plan, enter a phone number, and pay."
            : "Choose a plan, enter a phone number, and pay. If staff gave you a customer ID, you can add it later only when needed."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[var(--portal-accent)]/35 bg-black/35 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="font-medium text-white">This device is already remembered</p>
        <p className="mt-1 text-white/75">You usually won&apos;t need to type your customer ID again on this phone.</p>
        <details className="mt-2 text-xs text-white/65">
          <summary className="cursor-pointer list-none text-[var(--portal-accent)]">Show support details</summary>
          <p className="mt-2 font-mono break-all text-white/80">{customerId}</p>
        </details>
      </div>
      <button
        type="button"
        className="shrink-0 rounded-lg border border-white/20 px-3 py-2 text-xs font-medium text-[var(--portal-accent)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--portal-accent)]"
        onClick={() => {
          clearStoredCustomerId(siteSlug);
          setCustomerId(null);
        }}
      >
        Clear from this device
      </button>
    </div>
  );
}
