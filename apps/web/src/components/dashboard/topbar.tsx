"use client";

import Link from "next/link";
import { ChevronDown, LogOut, Menu, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth/auth-context";

export function DashboardTopbar({
  title,
  mobileNavOpen = false,
  onOpenMobileNav,
}: {
  title: string;
  mobileNavOpen?: boolean;
  onOpenMobileNav?: () => void;
}) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b bg-card/90 px-4 backdrop-blur-md sm:h-16 sm:px-6 md:px-8">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="shrink-0 border-esn-olive/25 lg:hidden"
          onClick={() => onOpenMobileNav?.()}
          aria-label="Open navigation menu"
          aria-controls="dashboard-sidebar"
          aria-expanded={mobileNavOpen}
        >
          <Menu className="h-5 w-5" aria-hidden />
        </Button>
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground sm:text-xs">ESN Admin</p>
          <h1 className="truncate font-display text-lg font-semibold tracking-tight text-foreground sm:text-xl">{title}</h1>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <Button variant="outline" size="sm" asChild className="hidden border-esn-olive/20 sm:inline-flex">
          <Link href="/">Home</Link>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="olive" className="gap-2 bg-esn-olive hover:bg-esn-olive-light" aria-label="Account menu">
              <User className="h-4 w-4 shrink-0" aria-hidden />
              <span className="hidden max-w-[120px] truncate sm:inline">{user?.full_name || "Account"}</span>
              <ChevronDown className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="truncate text-xs font-normal text-muted-foreground">{user?.email}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings" className="cursor-pointer">
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer text-destructive focus:text-destructive"
              onClick={() => {
                logout();
                window.location.href = "/login";
              }}
            >
              <LogOut className="mr-2 h-4 w-4" aria-hidden />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
