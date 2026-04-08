"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/dashboard/empty-state";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet } from "@/lib/api/client";
import type { SessionListRow } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

export function SessionsList() {
  const [activeOnly, setActiveOnly] = useState(true);
  const q = useQuery({
    queryKey: ["sessions", activeOnly],
    queryFn: () => apiGet<SessionListRow[]>(`/sessions?active_only=${activeOnly}`),
  });

  if (q.isLoading) return <QueryLoading rows={5} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle className="font-display text-lg">Hotspot sessions</CardTitle>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
            Active only
          </label>
        </CardHeader>
        <CardContent>
          {!q.data?.length ? (
            <EmptyState icon={Activity} title="No sessions" description="Toggle off “Active only” to see history." />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Login</TableHead>
                    <TableHead>MAC</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Router</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {q.data.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="whitespace-nowrap text-sm">{formatDate(s.login_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{s.mac_address}</TableCell>
                      <TableCell>{s.username ?? "—"}</TableCell>
                      <TableCell className="font-mono text-xs">{s.router_id.slice(0, 8)}…</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{s.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
