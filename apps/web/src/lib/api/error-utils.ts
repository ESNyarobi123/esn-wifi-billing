import { ApiRequestError } from "@/lib/api/client";

/** Consistent copy for UI toasts, alerts, and form errors. */
export function userFacingApiMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 429) return "Too many requests. Please wait a moment and try again.";
    if (error.status === 403) return "You don't have permission to do that.";
    if (error.status === 401) return "Your session expired. Please sign in again.";
    if (error.status === 404) return "That resource was not found.";
    if (error.status >= 500) {
      return error.message || "The server had a problem. Try again in a little while.";
    }
    return error.message || "Request failed.";
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function isRateLimitedError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 429;
}

export function isForbiddenError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 403;
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 401;
}
