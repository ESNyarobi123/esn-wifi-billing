import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: { label: string; href: string };
}) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/10 px-4 py-12 text-center sm:py-16"
      role="status"
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted" aria-hidden>
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>
      <p className="mt-2 max-w-md text-pretty text-sm text-muted-foreground">{description}</p>
      {action && (
        <Button className="mt-6 min-h-11 px-6" asChild>
          <a href={action.href}>{action.label}</a>
        </Button>
      )}
    </div>
  );
}
