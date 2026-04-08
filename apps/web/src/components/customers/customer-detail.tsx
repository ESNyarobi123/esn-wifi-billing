"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { CreditCard, KeyRound, Router, Smartphone } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { apiGet } from "@/lib/api/client";
import { formatDate, formatMoney } from "@/lib/format";
import { paymentStatusVariant } from "@/lib/payment-badge";

type CustomerDetail = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  account_status: string;
  site_id: string | null;
  devices: { id: string; mac_address: string; hostname: string | null }[];
  payments: {
    id: string;
    order_reference: string;
    amount: string;
    currency: string;
    payment_status: string;
    created_at: string;
  }[];
  access_grants: Record<string, unknown>[];
  vouchers: { id: string; code: string; status: string; plan_id: string }[];
  session_history: {
    id: string;
    router_id: string;
    mac_address: string;
    login_at: string;
    status: string;
    bytes_up: number;
    bytes_down: number;
  }[];
};

export function CustomerDetail({ customerId }: { customerId: string }) {
  const q = useQuery({
    queryKey: ["customer", customerId],
    queryFn: () => apiGet<CustomerDetail>(`/customers/${customerId}`),
  });

  if (q.isLoading) return <QueryLoading rows={6} />;
  if (q.error) return <QueryError error={q.error as Error} retry={() => void q.refetch()} />;

  const c = q.data!;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl font-bold">{c.full_name || "Customer"}</h2>
          <p className="text-sm text-muted-foreground">{c.email ?? c.phone ?? c.id}</p>
          <Badge className="mt-2" variant="outline">
            {c.account_status}
          </Badge>
        </div>
        <Button variant="outline" asChild>
          <Link href="/dashboard/customers">Back to list</Link>
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <KeyRound className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Access grants</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {!c.access_grants.length && <p className="text-muted-foreground">No grants yet.</p>}
            {c.access_grants.map((g, i) => (
              <pre key={i} className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
                {JSON.stringify(g, null, 2)}
              </pre>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2">
            <Smartphone className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Devices</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>MAC</TableHead>
                  <TableHead>Hostname</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {c.devices.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-mono text-xs">{d.mac_address}</TableCell>
                    <TableCell>{d.hostname ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!c.devices.length && <p className="text-sm text-muted-foreground">No devices.</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <CreditCard className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">Payments</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Reference</TableHead>
                <TableHead>When</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {c.payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/dashboard/payments/${p.id}`} className="font-mono text-xs text-primary hover:underline">
                      {p.order_reference}
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm">{formatDate(p.created_at)}</TableCell>
                  <TableCell>{formatMoney(p.amount, p.currency)}</TableCell>
                  <TableCell>
                    <Badge variant={paymentStatusVariant(p.payment_status)}>{p.payment_status}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!c.payments.length && <p className="text-sm text-muted-foreground">No payments.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <Router className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">Vouchers & sessions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h4 className="mb-2 text-sm font-medium">Vouchers</h4>
            <div className="flex flex-wrap gap-2">
              {c.vouchers.map((v) => (
                <Badge key={v.id} variant="secondary">
                  {v.code} · {v.status}
                </Badge>
              ))}
              {!c.vouchers.length && <span className="text-sm text-muted-foreground">None</span>}
            </div>
          </div>
          <Separator />
          <div>
            <h4 className="mb-2 text-sm font-medium">Session history</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Login</TableHead>
                  <TableHead>MAC</TableHead>
                  <TableHead>Router</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {c.session_history.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="text-sm">{formatDate(s.login_at)}</TableCell>
                    <TableCell className="font-mono text-xs">{s.mac_address}</TableCell>
                    <TableCell className="font-mono text-xs">{s.router_id.slice(0, 8)}…</TableCell>
                    <TableCell>{s.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!c.session_history.length && <p className="text-sm text-muted-foreground">No sessions.</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
