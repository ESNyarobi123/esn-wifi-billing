"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  title: string;
  description: string;
  variant?: "rate_limit" | "generic";
  onRetry?: () => void;
};

export function PortalInlineError({ title, description, variant = "generic", onRetry }: Props) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        variant === "rate_limit"
          ? "border-amber-400/40 bg-amber-500/10 text-amber-50"
          : "border-white/20 bg-white/5 text-white"
      }`}
      role="alert"
    >
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
        <div className="min-w-0 space-y-2">
          <h2 className="font-display text-base font-semibold leading-tight">{title}</h2>
          <p className="text-pretty text-sm leading-relaxed opacity-90">{description}</p>
          {onRetry && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-2 border-white/30 bg-white/10 text-white hover:bg-white/20"
              onClick={onRetry}
            >
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
