import { VoucherBatchDetail } from "@/components/vouchers/voucher-batch-detail";

export default async function Page({ params }: { params: Promise<{ batchId: string }> }) {
  const { batchId } = await params;
  return <VoucherBatchDetail batchId={batchId} />;
}
