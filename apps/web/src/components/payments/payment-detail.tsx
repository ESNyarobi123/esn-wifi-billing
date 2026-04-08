"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";
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
import { QueryError, QueryLoading } from "@/components/dashboard/query-boundary";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { apiGet, apiPost } from "@/lib/api/client";
import { userFacingApiMessage } from "@/lib/api/error-utils";
import type { PaymentDetail, PaymentEventRow } from "@/lib/api/types";
import { formatDate, formatMoney } from "@/lib/format";
import { paymentStatusAriaLabel, paymentStatusVariant } from "@/lib/payment-badge";

export function PaymentDetailView({ paymentId }: { paymentId: string }) {
  const qc = useQueryClient();
  const payQ = useQuery({
    queryKey: ["payment", paymentId],
    queryFn: () => apiGet<PaymentDetail>(`/payments/${paymentId}`),
  });
  const evQ = useQuery({
    queryKey: ["payment", paymentId, "events"],
    queryFn: () => apiGet<PaymentEventRow[]>(`/payments/${paymentId}/events`),
  });

  const mockComplete = useMutation({
    mutationFn: (orderRef: string) => apiPost<{ activation: unknown }>("/payments/mock/complete", { order_reference: orderRef }),
    onSuccess: () => {
      toast.success("Mock payment completed");
      void qc.invalidateQueries({ queryKey: ["payment", paymentId] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const markSuccess = useMutation({
    mutationFn: () => apiPost<{ activation: unknown }>(`/payments/${paymentId}/mark-success`),
    onSuccess: () => {
      toast.success("Marked successful");
      void qc.invalidateQueries({ queryKey: ["payment", paymentId] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  const refreshProvider = useMutation({
    mutationFn: () => apiPost<{ payment_status: string; gateway_status: string | null }>(`/payments/${paymentId}/refresh-status`),
    onSuccess: (data) => {
      toast.success(data.gateway_status ? `Provider status: ${data.gateway_status}` : "Provider status refreshed");
      void qc.invalidateQueries({ queryKey: ["payment", paymentId] });
      void qc.invalidateQueries({ queryKey: ["payment", paymentId, "events"] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e: Error) => toast.error(userFacingApiMessage(e)),
  });

  if (payQ.isLoading) return <QueryLoading rows={4} />;
  if (payQ.error) return <QueryError error={payQ.error as Error} retry={() => void payQ.refetch()} />;

  const p = payQ.data!;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" asChild>
          <Link href="/dashboard/payments">← Payments</Link>
        </Button>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={refreshProvider.isPending || mockComplete.isPending || markSuccess.isPending} onClick={() => refreshProvider.mutate()}>
            <RefreshCw className={`h-4 w-4 ${refreshProvider.isPending ? "animate-spin" : ""}`} aria-hidden />
            Refresh provider status
          </Button>
          {p.provider === "mock" && p.payment_status !== "success" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="secondary" disabled={mockComplete.isPending || markSuccess.isPending}>
                  Mock complete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Complete mock payment?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This simulates gateway success for testing. It only works for mock provider payments.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => mockComplete.mutate(p.order_reference)}>Confirm</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
          {p.payment_status !== "success" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" disabled={markSuccess.isPending || mockComplete.isPending}>
                  Mark success (override)
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Force successful payment?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Use only when reconciling with your PSP. This will run the success pipeline as if the provider
                    confirmed payment.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={() => markSuccess.mutate()}
                  >
                    Confirm override
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-xl">{p.order_reference}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant={paymentStatusVariant(p.payment_status)} aria-label={paymentStatusAriaLabel(p.payment_status)}>
              {p.payment_status}
            </Badge>
            <Badge variant="outline" aria-label={`Payment provider: ${p.provider}`}>
              {p.provider}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm md:grid-cols-2">
          <div>
            <span className="text-muted-foreground">Amount</span>
            <p className="font-medium">{formatMoney(p.amount, p.currency)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Created</span>
            <p className="font-medium">{formatDate(p.created_at)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Customer</span>
            <p className="font-mono text-xs">{p.customer_id ?? "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Plan</span>
            <p className="font-mono text-xs">{p.plan_id ?? "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Provider reference</span>
            <p className="font-mono text-xs">{p.provider_ref ?? "—"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(p.metadata ?? {}, null, 2)}</pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Event timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {evQ.isLoading && <p className="text-sm text-muted-foreground">Loading events…</p>}
          {evQ.error && <p className="text-sm text-destructive">Could not load events.</p>}
          <div className="-mx-2 overflow-x-auto rounded-lg border border-border/60 md:mx-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Payload</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {evQ.data?.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap text-sm">{formatDate(e.created_at)}</TableCell>
                  <TableCell>{e.event_type}</TableCell>
                  <TableCell className="max-w-md truncate font-mono text-xs">{JSON.stringify(e.payload)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </div>
          {!evQ.data?.length && !evQ.isLoading && <p className="text-sm text-muted-foreground">No events.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
