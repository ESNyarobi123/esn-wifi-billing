"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { Badge } from "@/components/ui/badge";
import { apiGet } from "@/lib/api/client";

type OperationalOverview = {
  router_id: string;
  name: string;
  site_id: string;
  is_online: boolean;
  last_seen_at: string | null;
  last_sync_at: string | null;
  active_sessions: number;
  latest_snapshot: {
    cpu_load_percent: number | null;
    free_memory_bytes: number | null;
    total_memory_bytes: number | null;
    uptime_seconds: number | null;
    created_at: string;
  } | null;
};

export function RouterStatusView({ routerId }: { routerId: string }) {
  const q = useQuery({
    queryKey: ["router", routerId, "ops"],
    queryFn: () => apiGet<OperationalOverview>(`/routers/${routerId}/status`),
  });

  if (q.isLoading) return <QueryLoading rows={3} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const d = q.data!;
  const snap = d.latest_snapshot;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">Operational</CardTitle>
          <CardDescription>{d.name}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row label="Reachable" value={<Badge variant={d.is_online ? "success" : "destructive"}>{d.is_online ? "Yes" : "No"}</Badge>} />
          <Row label="Active sessions" value={String(d.active_sessions)} />
          <Row label="Last seen" value={d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"} />
          <Row label="Last successful sync" value={d.last_sync_at ? new Date(d.last_sync_at).toLocaleString() : "—"} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">Latest NAS snapshot</CardTitle>
          <CardDescription>Most recent sync payload</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {!snap ? (
            <p className="text-muted-foreground">No snapshot yet — run sync.</p>
          ) : (
            <ul className="space-y-2">
              <Row label="Recorded" value={new Date(snap.created_at).toLocaleString()} />
              <Row label="CPU load %" value={snap.cpu_load_percent != null ? String(snap.cpu_load_percent) : "—"} />
              <Row
                label="Memory"
                value={
                  snap.free_memory_bytes != null && snap.total_memory_bytes != null
                    ? `${(snap.free_memory_bytes / 1e6).toFixed(1)} / ${(snap.total_memory_bytes / 1e6).toFixed(1)} MB free`
                    : "—"
                }
              />
              <Row label="Uptime (s)" value={snap.uptime_seconds != null ? String(snap.uptime_seconds) : "—"} />
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
