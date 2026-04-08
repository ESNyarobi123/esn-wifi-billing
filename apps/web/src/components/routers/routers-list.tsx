"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, RefreshCw, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { apiGet, apiPost } from "@/lib/api/client";
import type { RouterRow, SiteRow } from "@/lib/api/types";
import { useState } from "react";

export function RoutersList() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["routers"], queryFn: () => apiGet<RouterRow[]>("/routers") });
  const sitesQ = useQuery({ queryKey: ["sites"], queryFn: () => apiGet<SiteRow[]>("/sites") });

  if (q.isLoading) return <QueryLoading rows={5} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Manage NAS endpoints and live operations.</p>
        <CreateRouterDialog sites={sitesQ.data ?? []} onCreated={() => void qc.invalidateQueries({ queryKey: ["routers"] })} />
      </div>
      {!q.data?.length ? (
        <EmptyState icon={Wifi} title="No routers" description="Register your first MikroTik router to begin." />
      ) : (
        <Card className="border-border/80">
          <CardHeader>
            <CardTitle className="font-display text-lg">All routers</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Host</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {r.host}:{r.api_port}
                      {r.use_tls ? " (TLS)" : ""}
                    </TableCell>
                    <TableCell>
                      <Badge variant={r.is_online ? "success" : "destructive"}>{r.is_online ? "Online" : "Offline"}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {r.last_seen_at ? new Date(r.last_seen_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/dashboard/routers/${r.id}`}>View</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function CreateRouterDialog({ sites, onCreated }: { sites: SiteRow[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [siteId, setSiteId] = useState("");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("8728");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [useTls, setUseTls] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!siteId) {
      toast.error("Select a site");
      return;
    }
    setBusy(true);
    try {
      await apiPost("/routers", {
        site_id: siteId,
        name,
        host,
        api_port: Number.parseInt(port, 10) || 8728,
        username,
        password,
        use_tls: useTls,
      });
      toast.success("Router created");
      setOpen(false);
      onCreated();
      setName("");
      setHost("");
      setPassword("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Plus className="h-4 w-4" />
          Add router
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display">Register router</DialogTitle>
        </DialogHeader>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1">
            <Label>Site</Label>
            <select
              required
              className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
              value={siteId}
              onChange={(e) => setSiteId(e.target.value)}
            >
              <option value="">Choose site…</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.slug})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <Label>Host</Label>
            <Input value={host} onChange={(e) => setHost(e.target.value)} required placeholder="192.168.88.1" />
          </div>
          <div className="flex gap-2">
            <div className="flex-1 space-y-1">
              <Label>API port</Label>
              <Input value={port} onChange={(e) => setPort(e.target.value)} />
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={useTls} onChange={(e) => setUseTls(e.target.checked)} />
                TLS
              </label>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Username</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} required autoComplete="off" />
          </div>
          <div className="space-y-1">
            <Label>Password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" /> Saving…
              </>
            ) : (
              "Create"
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
