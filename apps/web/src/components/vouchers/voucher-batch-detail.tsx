"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet } from "@/lib/api/client";
import type { VoucherBatchDetail } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

export function VoucherBatchDetail({ batchId }: { batchId: string }) {
  const q = useQuery({
    queryKey: ["voucher-batch", batchId],
    queryFn: () => apiGet<VoucherBatchDetail>(`/voucher-batches/${batchId}`),
  });

  if (q.isLoading) return <QueryLoading rows={3} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const b = q.data!;

  return (
    <div className="space-y-6">
      <Button variant="outline" asChild>
        <Link href="/dashboard/vouchers">← Vouchers</Link>
      </Button>
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-xl">{b.name}</CardTitle>
          <p className="text-sm text-muted-foreground">Created {formatDate(b.created_at)}</p>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Qty {b.quantity}</Badge>
            <Badge variant="secondary">Total vouchers {b.voucher_total}</Badge>
            <Badge variant="muted">{b.status}</Badge>
          </div>
          <div>
            <p className="font-medium text-foreground">By status</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(b.vouchers_by_status).map(([k, v]) => (
                <Badge key={k} variant="outline">
                  {k}: {v}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
