"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { CreditCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { PaymentListRow } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { paymentStatusVariant } from "@/lib/payment-badge";

export function PaymentsList() {
  const q = useQuery({ queryKey: ["payments"], queryFn: () => apiGet<PaymentListRow[]>("/payments?limit=150") });

  if (q.isLoading) return <QueryLoading rows={5} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-display text-lg">Payments</CardTitle>
      </CardHeader>
      <CardContent>
        {!q.data?.length ? (
          <EmptyState icon={CreditCard} title="No payments" description="Checkout activity will land here." />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reference</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">{p.order_reference}</TableCell>
                    <TableCell>{p.provider}</TableCell>
                    <TableCell>{formatMoney(p.amount, p.currency)}</TableCell>
                    <TableCell>
                      <Badge variant={paymentStatusVariant(p.payment_status)}>{p.payment_status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/dashboard/payments/${p.id}`}>Open</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
