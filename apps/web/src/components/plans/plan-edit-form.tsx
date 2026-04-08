"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet, apiPatch, apiPut } from "@/lib/api/client";
import type { PlanDetail, RouterRow } from "@/lib/api/types";

export function PlanEditForm({ planId }: { planId: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const planQ = useQuery({ queryKey: ["plan", planId], queryFn: () => apiGet<PlanDetail>(`/plans/${planId}`) });
  const routersQ = useQuery({ queryKey: ["routers"], queryFn: () => apiGet<RouterRow[]>("/routers") });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [planType, setPlanType] = useState("time");
  const [duration, setDuration] = useState("");
  const [dataQuota, setDataQuota] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("TZS");
  const [isActive, setIsActive] = useState(true);
  const [selectedRouters, setSelectedRouters] = useState<Set<string>>(new Set());

  useEffect(() => {
    const p = planQ.data;
    if (!p) return;
    setName(p.name);
    setDescription(p.description ?? "");
    setPlanType(p.plan_type);
    setDuration(p.duration_seconds != null ? String(p.duration_seconds) : "");
    setDataQuota(p.data_bytes_quota != null ? String(p.data_bytes_quota) : "");
    setPrice(p.price_amount);
    setCurrency(p.currency);
    setIsActive(p.is_active);
    setSelectedRouters(new Set(p.router_ids));
  }, [planQ.data]);

  const savePlan = useMutation({
    mutationFn: async () => {
      const patch: Record<string, unknown> = {
        name,
        description: description || null,
        plan_type: planType,
        price_amount: price,
        currency,
        is_active: isActive,
      };
      if (planType === "time") patch.duration_seconds = Number.parseInt(duration, 10) || null;
      if (planType === "data") patch.data_bytes_quota = Number.parseInt(dataQuota, 10) || null;
      await apiPatch(`/plans/${planId}`, patch);
      await apiPut(`/plans/${planId}/routers`, { router_ids: [...selectedRouters] });
    },
    onSuccess: () => {
      toast.success("Plan saved");
      void qc.invalidateQueries({ queryKey: ["plan", planId] });
      void qc.invalidateQueries({ queryKey: ["plans"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (planQ.isLoading || !planQ.data) return <QueryLoading rows={5} />;
  if (planQ.error) return <QueryError error={planQ.error as Error} retry={() => void planQ.refetch()} />;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="border-border/80">
        <CardHeader>
          <CardTitle className="font-display">Plan details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Type</Label>
            <select className="flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm" value={planType} onChange={(e) => setPlanType(e.target.value)}>
              <option value="time">Time</option>
              <option value="data">Data</option>
              <option value="unlimited">Unlimited</option>
            </select>
          </div>
          {planType === "time" && (
            <div className="space-y-1">
              <Label>Duration (seconds)</Label>
              <Input value={duration} onChange={(e) => setDuration(e.target.value)} type="number" />
            </div>
          )}
          {planType === "data" && (
            <div className="space-y-1">
              <Label>Data quota (bytes)</Label>
              <Input value={dataQuota} onChange={(e) => setDataQuota(e.target.value)} type="number" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>Price</Label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input value={currency} onChange={(e) => setCurrency(e.target.value)} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={isActive} onCheckedChange={(v) => setIsActive(v === true)} />
            Active
          </label>
          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => router.push("/dashboard/plans")}>
              Done
            </Button>
            <Button type="button" onClick={() => savePlan.mutate()} disabled={savePlan.isPending}>
              {savePlan.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/80">
        <CardHeader>
          <CardTitle className="font-display">Router availability</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {routersQ.data?.map((r) => (
            <label key={r.id} className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/60 p-3">
              <Checkbox
                checked={selectedRouters.has(r.id)}
                onCheckedChange={(v) => {
                  const next = new Set(selectedRouters);
                  if (v === true) next.add(r.id);
                  else next.delete(r.id);
                  setSelectedRouters(next);
                }}
              />
              <div className="text-sm">
                <div className="font-medium">{r.name}</div>
                <div className="text-xs text-muted-foreground">{r.host}</div>
              </div>
            </label>
          ))}
          {!routersQ.data?.length && <p className="text-sm text-muted-foreground">No routers to attach.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
