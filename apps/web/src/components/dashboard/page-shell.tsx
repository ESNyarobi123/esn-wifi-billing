"use client";

import { useState, type ReactNode } from "react";
import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { DashboardTopbar } from "@/components/dashboard/topbar";

export function PageShell({ title, children }: { title: string; children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <button
        type="button"
        className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px] transition-opacity lg:hidden ${mobileNavOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        aria-hidden={!mobileNavOpen}
        tabIndex={-1}
        onClick={() => setMobileNavOpen(false)}
      />
      <DashboardSidebar mobileOpen={mobileNavOpen} onNavigate={() => setMobileNavOpen(false)} />
      <div className="min-h-screen lg:pl-60">
        <DashboardTopbar
          title={title}
          mobileNavOpen={mobileNavOpen}
          onOpenMobileNav={() => setMobileNavOpen(true)}
        />
        <main className="mx-auto max-w-[1600px] p-4 pb-12 sm:p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
