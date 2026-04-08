"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function RouterSubnav({ routerId }: { routerId: string }) {
  const pathname = usePathname();
  const base = `/dashboard/routers/${routerId}`;
  const tabs = [
    { href: base, label: "Overview" },
    { href: `${base}/status`, label: "Status" },
    { href: `${base}/snapshots`, label: "Snapshots" },
    { href: `${base}/sessions`, label: "Live sessions" },
  ];

  return (
    <nav className="mb-6 flex flex-wrap gap-2 border-b border-border pb-3">
      {tabs.map(({ href, label }) => {
        const isActive = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
