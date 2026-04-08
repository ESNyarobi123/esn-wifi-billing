"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiGet } from "@/lib/api/client";

type Snap = {
  id: string;
  cpu_load_percent: number | null;
  free_memory_bytes: number | null;
  total_memory_bytes: number | null;
  uptime_seconds: number | null;
  created_at: string;
};

export function RouterSnapshots({ routerId }: { routerId: string }) {
  const q = useQuery({
    queryKey: ["router", routerId, "snapshots"],
    queryFn: () => apiGet<Snap[]>(`/routers/${routerId}/snapshots?limit=50`),
  });

  if (q.isLoading) return <QueryLoading rows={4} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <Card className="border-border/80">
      <CardHeader>
        <CardTitle className="font-display text-lg">Health snapshots</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>CPU %</TableHead>
              <TableHead>Uptime</TableHead>
              <TableHead>Free mem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {q.data?.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="text-sm">{new Date(s.created_at).toLocaleString()}</TableCell>
                <TableCell>{s.cpu_load_percent ?? "—"}</TableCell>
                <TableCell>{s.uptime_seconds ?? "—"}</TableCell>
                <TableCell>{s.free_memory_bytes != null ? `${(s.free_memory_bytes / 1e6).toFixed(1)} MB` : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {!q.data?.length && <p className="py-8 text-center text-sm text-muted-foreground">No snapshots recorded.</p>}
      </CardContent>
    </Card>
  );
}
