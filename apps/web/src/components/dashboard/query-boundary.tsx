"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";

export function QueryLoading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-label="Loading">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-14 w-full rounded-lg" />
      ))}
    </div>
  );
}

export function QueryError({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  const msg = userFacingApiMessage(error);
  const is429 = error instanceof ApiRequestError && error.status === 429;
  const is403 = error instanceof ApiRequestError && error.status === 403;
  const is401 = error instanceof ApiRequestError && error.status === 401;
  const isOffline = error instanceof ApiRequestError && error.status === 0;

  let title = "Something went wrong";
  if (is429) title = "Too many requests";
  if (is403) title = "Access denied";
  if (is401) title = "Session expired";
  if (isOffline) title = "Connection problem";

  return (
    <Alert variant={is429 ? "warning" : "destructive"} role="alert">
      <AlertCircle className="h-4 w-4" aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <span className="text-pretty">{msg}</span>
        {retry && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => retry()}
            className="shrink-0 gap-2 bg-card"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
