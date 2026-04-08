"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Bell,
  CreditCard,
  Radio,
  Router,
  TrendingUp,
  WifiOff,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/dashboard/empty-state";
import { OverviewSkeleton } from "@/components/dashboard/overview-skeleton";
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import { StatCard } from "@/components/dashboard/stat-card";
import { ApiRequestError, apiGet, apiPost } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import type { AnalyticsOverview, NotificationRow, PaymentListRow } from "@/lib/api/types";
import { formatMoney, shortId } from "@/lib/format";
import { paymentStatusAriaLabel, paymentStatusVariant } from "@/lib/payment-badge";
import { toast } from "sonner";

const CHART_COLORS = ["#FBA002", "#313B2F", "#4a5a46", "#2d6a4f", "#bc6c25"];

export function OverviewDashboard() {
  const qc = useQueryClient();

  const overviewQ = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: () => apiGet<AnalyticsOverview>("/analytics/overview"),
  });

  const notificationsQ = useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiGet<NotificationRow[]>("/notifications"),
    retry: (n, err) => {
      if (err instanceof ApiRequestError && (err.status === 403 || err.status === 401)) return false;
      return n < 2;
    },
  });

  const paymentsQ = useQuery({
    queryKey: ["payments", "recent"],
    queryFn: () => apiGet<PaymentListRow[]>("/payments?limit=12"),
  });

  const markRead = useMutation({
    mutationFn: (id: string) => apiPost(`/notifications/${id}/read`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  if (overviewQ.isLoading) {
    return <OverviewSkeleton />;
  }

  if (overviewQ.error) {
    return (
      <QueryError
        error={overviewQ.error as Error}
        retry={() => void overviewQ.refetch()}
      />
    );
  }

  const o = overviewQ.data!;
  const routers = o.routers ?? [];
  const totalRouters = routers.length;
  const onlineRouters = routers.filter((r) => r.is_online).length;
  const offlineRouters = totalRouters - onlineRouters;

  const revData = [
    { label: "Today", value: Number.parseFloat(o.revenue.today) || 0 },
    { label: "Week", value: Number.parseFloat(o.revenue.week_to_date) || 0 },
    { label: "Month", value: Number.parseFloat(o.revenue.month_to_date) || 0 },
  ];

  const payPie = Object.entries(o.payments_by_status || {}).map(([name, value]) => ({
    name,
    value: Number(value) || 0,
  }));

  return (
    <div className="space-y-8">
      <motion.div
        className="flex flex-wrap items-end justify-between gap-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div>
          <p className="text-sm font-medium text-muted-foreground">Operations overview</p>
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Network health & revenue
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/dashboard/routers">Routers</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/dashboard/payments">
              Payments <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </motion.div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Routers online" value={`${onlineRouters} / ${totalRouters}`} sub={`${offlineRouters} offline`} icon={Router} delay={0} />
        <StatCard title="Active sessions" value={o.sessions.active} icon={Activity} delay={0.05} />
        <StatCard title="Revenue (month)" value={formatMoney(o.revenue.month_to_date)} icon={TrendingUp} delay={0.1} />
        <StatCard title="New customers (period)" value={o.customers.new_in_period} sub={`${o.customers.total_customers} total`} icon={Radio} delay={0.15} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 border-border/80 shadow-sm">
          <CardHeader>
            <CardTitle className="font-display text-lg">Revenue pulse</CardTitle>
            <CardDescription>Successful payments aggregate</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="label" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} width={48} />
                <Tooltip
                  formatter={(v: number) => [formatMoney(String(v)), "Amount"]}
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} fill="#FBA002" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-border/80 shadow-sm">
          <CardHeader>
            <CardTitle className="font-display text-lg">Payments by status</CardTitle>
            <CardDescription>Current distribution</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {payPie.length === 0 ? (
              <EmptyState icon={CreditCard} title="No payment data" description="Status counts will appear once payments exist." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={payPie} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={52} outerRadius={80} paddingAngle={2}>
                    {payPie.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-border/80 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="font-display text-lg">Alerts & notifications</CardTitle>
              <CardDescription>Stay ahead of router and billing events</CardDescription>
            </div>
            <Bell className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-3">
            {notificationsQ.isLoading && <QueryLoading rows={2} />}
            {notificationsQ.error && notificationsQ.error instanceof ApiRequestError && notificationsQ.error.status === 403 && (
              <p className="text-sm text-muted-foreground">Notifications require permission.</p>
            )}
            {notificationsQ.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>
            )}
            {notificationsQ.data?.map((n) => (
              <div
                key={n.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-border/60 bg-card/50 p-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold leading-tight">{n.title}</p>
                  {n.body && <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{n.body}</p>}
                  <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">{n.type}</p>
                </div>
                {!n.read_at && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="shrink-0 text-xs"
                    onClick={() => markRead.mutate(n.id)}
                    disabled={markRead.isPending}
                  >
                    Mark read
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/80 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="font-display text-lg">Recent payments</CardTitle>
              <CardDescription>Newest settlement attempts</CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/dashboard/payments">View all</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {paymentsQ.isLoading && <QueryLoading rows={3} />}
            {paymentsQ.data?.length === 0 && (
              <EmptyState icon={CreditCard} title="No payments yet" description="Successful checkouts will show here." />
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reference</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paymentsQ.data?.slice(0, 8).map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">
                      <Link className="text-primary hover:underline" href={`/dashboard/payments/${p.id}`}>
                        {p.order_reference}
                      </Link>
                    </TableCell>
                    <TableCell>{formatMoney(p.amount, p.currency)}</TableCell>
                    <TableCell>
                      <Badge variant={paymentStatusVariant(p.payment_status)} aria-label={paymentStatusAriaLabel(p.payment_status)}>
                        {p.payment_status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/80 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="font-display text-lg">Top plans</CardTitle>
            <CardDescription>By successful purchases in analytics window</CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/dashboard/plans">Manage plans</Link>
          </Button>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(o.top_plans ?? []).slice(0, 8).map((pl) => (
              <Badge key={pl.plan_id} variant="secondary" className="px-3 py-1.5 text-xs">
                {pl.name ?? shortId(pl.plan_id)} · {pl.purchases} sales
              </Badge>
            ))}
            {(o.top_plans ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">No plan sales in the selected analytics range.</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/80 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="font-display text-lg">Router summary</CardTitle>
            <CardDescription>Live snapshot from analytics</CardDescription>
          </div>
          <WifiOff className="h-5 w-5 text-muted-foreground" />
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {routers.length === 0 ? (
            <EmptyState
              icon={Router}
              title="No routers"
              description="Add a router to start monitoring sessions."
              action={{ label: "Open routers", href: "/dashboard/routers" }}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sessions</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {routers.slice(0, 12).map((r) => (
                  <TableRow key={r.router_id}>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell>
                      <Badge
                        variant={r.is_online ? "success" : "destructive"}
                        aria-label={r.is_online ? "Router status: online" : "Router status: offline"}
                      >
                        {r.is_online ? "Online" : "Offline"}
                      </Badge>
                    </TableCell>
                    <TableCell>{r.active_sessions}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {r.last_seen_at ? new Date(r.last_seen_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/dashboard/routers/${r.router_id}`}>Open</Link>
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
