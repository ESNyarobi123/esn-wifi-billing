"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Users } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/dashboard/empty-state";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet } from "@/lib/api/client";
import type { CustomerListRow } from "@/lib/api/types";

export function CustomersList() {
  const q = useQuery({
    queryKey: ["customers"],
    queryFn: () => apiGet<CustomerListRow[]>("/customers"),
  });

  if (q.isLoading) return <QueryLoading rows={5} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  return (
    <Card className="border-border/80">
      <CardHeader>
        <CardTitle className="font-display text-lg">Customers</CardTitle>
      </CardHeader>
      <CardContent>
        {!q.data?.length ? (
          <EmptyState icon={Users} title="No customers" description="Customers appear when they buy plans or redeem vouchers." />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Profile</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.full_name || "—"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{c.email ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{c.account_status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/dashboard/customers/${c.id}`}>View</Link>
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
