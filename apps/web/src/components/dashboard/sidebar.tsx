"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  CreditCard,
  Gauge,
  LayoutDashboard,
  Router,
  Settings,
  Ticket,
  Users,
  Wifi,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const items = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/routers", label: "Routers", icon: Router },
  { href: "/dashboard/customers", label: "Customers", icon: Users },
  { href: "/dashboard/plans", label: "Plans", icon: Wifi },
  { href: "/dashboard/vouchers", label: "Vouchers", icon: Ticket },
  { href: "/dashboard/payments", label: "Payments", icon: CreditCard },
  { href: "/dashboard/sessions", label: "Sessions", icon: Activity },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function DashboardSidebar({
  mobileOpen = false,
  onNavigate,
}: {
  mobileOpen?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <aside
      id="dashboard-sidebar"
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex w-[min(100vw-3rem,15rem)] flex-col border-r border-white/10 bg-sidebar text-sidebar-foreground shadow-xl transition-transform duration-200 ease-out lg:w-60 lg:shadow-none",
        mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
      )}
      aria-label="Main navigation"
    >
      <div className="flex h-14 items-center gap-2 border-b border-white/10 px-3 sm:h-16 sm:px-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary font-display text-sm font-bold text-primary-foreground">
          ESN
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-sm font-semibold tracking-tight">WiFi Billing</p>
          <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/60">Operations</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0 text-sidebar-foreground hover:bg-white/10 hover:text-white lg:hidden"
          onClick={() => onNavigate?.()}
          aria-label="Close menu"
        >
          <X className="h-5 w-5" aria-hidden />
        </Button>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2 sm:p-3">
        {items.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className="relative block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar"
              onClick={() => onNavigate?.()}
            >
              {active && (
                <motion.span
                  layoutId="nav-pill"
                  className="absolute inset-0 rounded-lg bg-white/10"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span
                className={cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "text-white" : "text-sidebar-foreground/75 hover:bg-white/5 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
                {label}
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 p-3 sm:p-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 rounded-lg bg-primary/20 px-3 py-2 text-xs font-medium text-primary outline-none ring-primary focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar"
          onClick={() => onNavigate?.()}
        >
          <Gauge className="h-4 w-4 shrink-0" aria-hidden />
          Control center
        </Link>
      </div>
    </aside>
  );
}
