import { CustomerDetail } from "@/components/customers/customer-detail";

export default async function CustomerPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = await params;
  return <CustomerDetail customerId={customerId} />;
}
