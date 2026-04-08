"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet, apiPost } from "@/lib/api/client";

export function RouterLiveSessions({ routerId }: { routerId: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["router", routerId, "live-sessions"],
    queryFn: () => apiGet<Record<string, unknown>>(`/routers/${routerId}/sessions`),
  });

  const [mac, setMac] = useState("");

  const disconnectM = useMutation({
    mutationFn: (m: string) => apiPost(`/routers/${routerId}/disconnect?mac=${encodeURIComponent(m)}`),
    onSuccess: () => {
      toast.success("Disconnect requested");
      void qc.invalidateQueries({ queryKey: ["router", routerId, "live-sessions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) return <QueryLoading rows={4} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const raw = q.data ?? {};
  const nas = (raw.nas as Record<string, unknown> | undefined) ?? {};
  const sessions = (raw.sessions as Record<string, unknown>[] | undefined) ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">NAS status</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-40 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(nas, null, 2)}</pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="font-display text-lg">Live sessions</CardTitle>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (mac) disconnectM.mutate(mac);
            }}
          >
            <Input className="font-mono text-xs" placeholder="MAC to disconnect" value={mac} onChange={(e) => setMac(e.target.value)} />
            <Button type="submit" variant="outline" size="sm" disabled={!mac || disconnectM.isPending}>
              Disconnect
            </Button>
          </form>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {sessions[0]
                  ? Object.keys(sessions[0]).map((k) => <TableHead key={k}>{k}</TableHead>)
                  : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((row, i) => (
                <TableRow key={i}>
                  {Object.values(row).map((v, j) => (
                    <TableCell key={j} className="max-w-[200px] truncate font-mono text-xs">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {sessions.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No sessions returned from NAS.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
