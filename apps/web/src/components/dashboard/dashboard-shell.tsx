"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { PageShell } from "@/components/dashboard/page-shell";

function titleFromPath(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length <= 1 || pathname === "/dashboard") return "Overview";
  const seg = parts[1];
  if (seg === "routers") {
    if (parts.length === 2) return "Routers";
    if (parts.length === 3) return "Router";
    if (parts[3] === "status") return "Router · Status";
    if (parts[3] === "snapshots") return "Router · Snapshots";
    if (parts[3] === "sessions") return "Router · Live sessions";
  }
  if (seg === "customers") {
    if (parts.length === 2) return "Customers";
    if (parts.length === 3) return "Customer";
  }
  if (seg === "plans") {
    if (parts.length === 2) return "Plans";
    if (parts[2] === "new") return "New plan";
    if (parts.length === 3) return "Edit plan";
  }
  if (seg === "vouchers") {
    if (parts.length === 2) return "Vouchers";
    if (parts[2] === "redeem") return "Redeem voucher";
    if (parts[2] === "batches" && parts.length === 4) return "Voucher batch";
  }
  if (seg === "payments") {
    if (parts.length === 2) return "Payments";
    if (parts.length === 3) return "Payment";
  }
  if (seg === "sessions") return "Sessions";
  if (seg === "settings") return "Settings";
  return "Dashboard";
}

export function DashboardShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return <PageShell title={titleFromPath(pathname)}>{children}</PageShell>;
}
