"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, Wifi } from "lucide-react";
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
import type { PlanListRow } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";

export function PlansList() {
  const q = useQuery({ queryKey: ["plans"], queryFn: () => apiGet<PlanListRow[]>("/plans") });

  if (q.isLoading) return <QueryLoading rows={4} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button asChild>
          <Link href="/dashboard/plans/new">
            <Plus className="h-4 w-4" /> New plan
          </Link>
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">Billing plans</CardTitle>
        </CardHeader>
        <CardContent>
          {!q.data?.length ? (
            <EmptyState icon={Wifi} title="No plans" description="Create plans to sell time or data access." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead className="text-right">Edit</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{p.plan_type}</Badge>
                    </TableCell>
                    <TableCell>{formatMoney(p.price_amount, p.currency)}</TableCell>
                    <TableCell>{p.is_active ? <Badge variant="success">Yes</Badge> : <Badge variant="muted">No</Badge>}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/dashboard/plans/${p.id}`}>Edit</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
