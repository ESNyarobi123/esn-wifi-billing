import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
      <p className="font-display text-sm font-semibold uppercase tracking-widest text-muted-foreground">404</p>
      <h1 className="font-display text-3xl font-bold text-foreground">This page isn&apos;t here</h1>
      <p className="max-w-md text-sm text-muted-foreground">The link may be wrong, or the resource was removed.</p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button asChild>
          <Link href="/">Home</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/dashboard">Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
