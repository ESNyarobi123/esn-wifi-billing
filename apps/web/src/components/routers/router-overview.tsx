"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Plug, RefreshCw, ShieldBan, ShieldPlus, Unplug, Waypoints } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RouterProvisioningDownload } from "@/components/routers/router-provisioning-download";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiDelete, apiGet, apiPost } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import type { RouterRow } from "@/lib/api/types";

type BlockedRow = { id: string; mac_address: string; reason: string | null; status: string };
type WhitelistRow = { id: string; mac_address: string; note: string | null };

export function RouterOverview({ routerId }: { routerId: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["router", routerId],
    queryFn: () => apiGet<RouterRow>(`/routers/${routerId}`),
  });
  const blockedQ = useQuery({
    queryKey: ["router", routerId, "blocked"],
    queryFn: () => apiGet<BlockedRow[]>(`/routers/${routerId}/blocked-devices`),
  });
  const whiteQ = useQuery({
    queryKey: ["router", routerId, "whitelist"],
    queryFn: () => apiGet<WhitelistRow[]>(`/routers/${routerId}/whitelisted-devices`),
  });

  const testM = useMutation({
    mutationFn: () => apiPost<Record<string, unknown>>(`/routers/${routerId}/test-connection`),
    onSuccess: () => toast.success("Connection test finished"),
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });
  const syncM = useMutation({
    mutationFn: () => apiPost<Record<string, unknown>>(`/routers/${routerId}/sync`),
    onSuccess: () => {
      toast.success("Sync completed");
      void qc.invalidateQueries({ queryKey: ["router", routerId] });
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });
  const ingestM = useMutation({
    mutationFn: (prune: boolean) => apiPost(`/routers/${routerId}/ingest-sessions?prune_missing=${prune}`),
    onSuccess: () => toast.success("Sessions ingested"),
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });
  const reconcileM = useMutation({
    mutationFn: () => apiPost(`/routers/${routerId}/reconcile-access-lists`),
    onSuccess: () => {
      toast.success("Router access lists reconciled");
      void blockedQ.refetch();
      void whiteQ.refetch();
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const [macBlock, setMacBlock] = useState("");
  const [macWhite, setMacWhite] = useState("");
  const [whiteNote, setWhiteNote] = useState("");

  const blockM = useMutation({
    mutationFn: (mac: string) => apiPost(`/routers/${routerId}/block-mac?mac=${encodeURIComponent(mac)}`),
    onSuccess: () => {
      toast.success("MAC blocked");
      setMacBlock("");
      void blockedQ.refetch();
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const unblockM = useMutation({
    mutationFn: (mac: string) => apiPost(`/routers/${routerId}/unblock-mac?mac=${encodeURIComponent(mac)}`),
    onSuccess: () => {
      toast.success("MAC unblocked");
      void blockedQ.refetch();
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const addWhiteM = useMutation({
    mutationFn: () =>
      apiPost(`/routers/${routerId}/whitelisted-devices`, { mac_address: macWhite, note: whiteNote || null }),
    onSuccess: () => {
      toast.success("Whitelisted");
      setMacWhite("");
      setWhiteNote("");
      void whiteQ.refetch();
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const remWhiteM = useMutation({
    mutationFn: (id: string) => apiDelete(`/whitelisted-devices/${id}`),
    onSuccess: () => {
      toast.success("Removed");
      void whiteQ.refetch();
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const [whitelistRemoveId, setWhitelistRemoveId] = useState<string | null>(null);

  if (q.isLoading) return <QueryLoading rows={4} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const r = q.data!;
  const opsPending = testM.isPending || syncM.isPending || ingestM.isPending || reconcileM.isPending;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Identity</CardTitle>
            <CardDescription>Router record</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Status</span>
              <Badge
                variant={r.is_online ? "success" : "destructive"}
                aria-label={r.is_online ? "Router status: online" : "Router status: offline"}
              >
                {r.is_online ? "Online" : "Offline"}
              </Badge>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Host</span>
              <span className="font-mono text-xs">
                {r.host}:{r.api_port}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">API model</span>
              <span>{r.use_tls ? "TLS" : "Plain"}</span>
            </div>
            <Button variant="link" className="h-auto p-0" asChild>
              <Link href={`/dashboard/routers/${routerId}/status`}>Operational details →</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Operations</CardTitle>
            <CardDescription>Safe controls (permissions enforced server-side)</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => testM.mutate()} disabled={opsPending}>
              {testM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Plug className="h-4 w-4" aria-hidden />}
              Test connection
            </Button>
            <Button variant="outline" size="sm" onClick={() => syncM.mutate()} disabled={opsPending}>
              {syncM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RefreshCw className="h-4 w-4" aria-hidden />}
              Sync snapshot
            </Button>
            <Button variant="secondary" size="sm" onClick={() => ingestM.mutate(false)} disabled={opsPending}>
              {ingestM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Unplug className="h-4 w-4" aria-hidden />}
              Ingest sessions
            </Button>
            <Button variant="outline" size="sm" onClick={() => reconcileM.mutate()} disabled={opsPending}>
              {reconcileM.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Waypoints className="h-4 w-4" aria-hidden />}
              Reconcile access lists
            </Button>
            <RouterProvisioningDownload routerId={routerId} routerName={r.name} />
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="sm" disabled={opsPending}>
                  Ingest + prune
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Ingest and prune missing sessions?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Prune removes sessions that no longer exist on the router. Only continue if you understand the impact
                    on reporting and billing.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={() => ingestM.mutate(true)}
                  >
                    Run with prune
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldBan className="h-4 w-4" /> Blocked devices
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              className="flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (macBlock) blockM.mutate(macBlock);
              }}
            >
              <Input
                placeholder="AA:BB:CC:DD:EE:FF"
                value={macBlock}
                onChange={(e) => setMacBlock(e.target.value)}
                className="max-w-xs font-mono text-xs"
              />
              <Button type="submit" size="sm" disabled={!macBlock || blockM.isPending || opsPending}>
                Block
              </Button>
            </form>
            <div className="-mx-1 overflow-x-auto rounded-lg border border-border/50">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>MAC</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">Unblock</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {blockedQ.data?.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="font-mono text-xs">{b.mac_address}</TableCell>
                    <TableCell>{b.status}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => unblockM.mutate(b.mac_address)}
                        disabled={unblockM.isPending || blockM.isPending}
                      >
                        Unblock
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
            {!blockedQ.data?.length && <p className="text-sm text-muted-foreground">No blocked MACs.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldPlus className="h-4 w-4" /> Whitelist
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <Label className="text-xs">MAC</Label>
                <Input
                  className="font-mono text-xs"
                  value={macWhite}
                  onChange={(e) => setMacWhite(e.target.value)}
                  placeholder="AA:BB:CC:DD:EE:FF"
                />
              </div>
              <div>
                <Label className="text-xs">Note</Label>
                <Input value={whiteNote} onChange={(e) => setWhiteNote(e.target.value)} placeholder="optional" />
              </div>
            </div>
            <Button size="sm" onClick={() => addWhiteM.mutate()} disabled={!macWhite || addWhiteM.isPending}>
              Add whitelist entry
            </Button>
            <div className="-mx-1 overflow-x-auto rounded-lg border border-border/50">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>MAC</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead className="text-right">Remove</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {whiteQ.data?.map((w) => (
                  <TableRow key={w.id}>
                    <TableCell className="font-mono text-xs">{w.mac_address}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{w.note ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setWhitelistRemoveId(w.id)} disabled={remWhiteM.isPending}>
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
            {!whiteQ.data?.length && <p className="text-sm text-muted-foreground">No whitelist entries.</p>}
          </CardContent>
        </Card>
      </div>

      <AlertDialog open={whitelistRemoveId !== null} onOpenChange={(open) => !open && setWhitelistRemoveId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove whitelist entry?</AlertDialogTitle>
            <AlertDialogDescription>The device will no longer bypass paid access rules on this router.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (whitelistRemoveId) remWhiteM.mutate(whitelistRemoveId);
                setWhitelistRemoveId(null);
              }}
            >
              Remove entry
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
