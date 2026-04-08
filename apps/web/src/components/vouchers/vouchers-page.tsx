"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { Ticket } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { userFacingApiMessage } from "@/lib/api/error-utils";
import type { PlanListRow, VoucherBatchListRow, VoucherListRow } from "@/lib/api/types";

function VouchersPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") === "vouchers" ? "vouchers" : "batches";

  const batchesQ = useQuery({
    queryKey: ["voucher-batches"],
    queryFn: () => apiGet<VoucherBatchListRow[]>("/voucher-batches"),
  });
  const vouchersQ = useQuery({
    queryKey: ["vouchers"],
    queryFn: () => apiGet<VoucherListRow[]>("/vouchers?limit=200"),
  });
  const plansQ = useQuery({ queryKey: ["plans"], queryFn: () => apiGet<PlanListRow[]>("/plans") });

  if (batchesQ.isLoading || vouchersQ.isLoading) return <QueryLoading rows={4} />;
  if (batchesQ.error) return <QueryError error={batchesQ.error as Error} retry={() => void batchesQ.refetch()} />;
  if (vouchersQ.error) return <QueryError error={vouchersQ.error as Error} retry={() => void vouchersQ.refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/dashboard/vouchers/redeem">Admin redeem</Link>
        </Button>
        <CreateBatchDialog plans={plansQ.data ?? []} />
      </div>
      <Tabs
        value={tab}
        onValueChange={(v) => router.replace(`/dashboard/vouchers?tab=${v}`, { scroll: false })}
      >
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="batches">Batches</TabsTrigger>
          <TabsTrigger value="vouchers">Vouchers</TabsTrigger>
        </TabsList>
        <TabsContent value="batches" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">Batches</CardTitle>
            </CardHeader>
            <CardContent>
              {!batchesQ.data?.length ? (
                <EmptyState icon={Ticket} title="No batches" description="Generate voucher batches for events or resellers." />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead className="text-right">Detail</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {batchesQ.data.map((b) => (
                      <TableRow key={b.id}>
                        <TableCell className="font-medium">{b.name}</TableCell>
                        <TableCell>{b.quantity}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" asChild>
                            <Link href={`/dashboard/vouchers/batches/${b.id}`}>Open</Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="vouchers" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">Recent vouchers</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Plan</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {vouchersQ.data?.map((v) => (
                    <TableRow key={v.id}>
                      <TableCell className="font-mono text-xs">{v.code}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{v.status}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{v.plan_id.slice(0, 8)}…</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export function VouchersPage() {
  return (
    <Suspense fallback={<QueryLoading rows={4} />}>
      <VouchersPageInner />
    </Suspense>
  );
}

function CreateBatchDialog({ plans }: { plans: PlanListRow[] }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [planId, setPlanId] = useState("");
  const [quantity, setQuantity] = useState("100");
  const [prefix, setPrefix] = useState("");
  const [requiresPin, setRequiresPin] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!planId) {
      toast.error("Pick a plan");
      return;
    }
    setBusy(true);
    try {
      await apiPost("/voucher-batches", {
        name,
        plan_id: planId,
        quantity: Number.parseInt(quantity, 10) || 1,
        prefix: prefix || null,
        requires_pin: requiresPin,
      });
      toast.success("Batch created");
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["voucher-batches"] });
      void qc.invalidateQueries({ queryKey: ["vouchers"] });
    } catch (err) {
      toast.error(userFacingApiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Create batch</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display">New voucher batch</DialogTitle>
        </DialogHeader>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <Label>Plan</Label>
            <select className="flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm" value={planId} onChange={(e) => setPlanId(e.target.value)} required>
              <option value="">Select…</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Quantity</Label>
            <Input type="number" min={1} max={50000} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Prefix (optional)</Label>
            <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} maxLength={8} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={requiresPin} onCheckedChange={(v) => setRequiresPin(v === true)} />
            Requires PIN
          </label>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
