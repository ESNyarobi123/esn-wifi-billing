"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4 py-12 text-center">
      <AlertTriangle className="h-10 w-10 text-destructive" aria-hidden />
      <div className="max-w-md">
        <h1 className="font-display text-xl font-semibold">Dashboard error</h1>
        <p className="mt-2 text-pretty text-sm text-muted-foreground">
          {error.message || "This screen failed to render. Your session is still valid — try reloading this section."}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <Button type="button" onClick={() => reset()}>
          Try again
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link href="/dashboard">Overview</Link>
        </Button>
      </div>
    </div>
  );
}
