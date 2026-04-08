"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPost } from "@/lib/api/client";

export function PlanCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [planType, setPlanType] = useState("time");
  const [duration, setDuration] = useState("3600");
  const [dataQuota, setDataQuota] = useState("");
  const [price, setPrice] = useState("0");
  const [currency, setCurrency] = useState("TZS");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        name,
        description: description || null,
        plan_type: planType,
        price_amount: price,
        currency,
      };
      if (planType === "time") body.duration_seconds = Number.parseInt(duration, 10) || 3600;
      if (planType === "data") body.data_bytes_quota = Number.parseInt(dataQuota, 10) || 1;
      /* unlimited: no duration / quota fields */
      const res = await apiPost<{ id: string }>("/plans", body);
      toast.success("Plan created");
      router.replace(`/dashboard/plans/${res.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-lg border-border/80">
      <CardHeader>
        <CardTitle className="font-display">New plan</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
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
              <Input value={duration} onChange={(e) => setDuration(e.target.value)} type="number" min={60} />
            </div>
          )}
          {planType === "data" && (
            <div className="space-y-1">
              <Label>Data quota (bytes)</Label>
              <Input value={dataQuota} onChange={(e) => setDataQuota(e.target.value)} type="number" min={1} required />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>Price</Label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input value={currency} onChange={(e) => setCurrency(e.target.value)} maxLength={8} />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Create"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
