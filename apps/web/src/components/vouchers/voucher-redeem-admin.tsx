"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPost } from "@/lib/api/client";

export function VoucherRedeemAdmin() {
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<unknown>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        code,
        pin: pin || null,
        customer_id: customerId,
      };
      if (siteId.trim()) body.site_id = siteId.trim();
      const res = await apiPost<unknown>("/vouchers/redeem", body);
      setResult(res);
      toast.success("Redeemed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-lg border-border/80">
      <CardHeader>
        <CardTitle className="font-display">Admin voucher redeem</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1">
            <Label>Code</Label>
            <Input value={code} onChange={(e) => setCode(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <Label>PIN (optional)</Label>
            <Input value={pin} onChange={(e) => setPin(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Customer ID (UUID)</Label>
            <Input value={customerId} onChange={(e) => setCustomerId(e.target.value)} required className="font-mono text-xs" />
          </div>
          <div className="space-y-1">
            <Label>Site ID (optional — enforces plan at site)</Label>
            <Input value={siteId} onChange={(e) => setSiteId(e.target.value)} className="font-mono text-xs" />
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? "Redeeming…" : "Redeem"}
          </Button>
        </form>
        {result != null && (
          <pre className="mt-4 max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(result, null, 2)}</pre>
        )}
      </CardContent>
    </Card>
  );
}
