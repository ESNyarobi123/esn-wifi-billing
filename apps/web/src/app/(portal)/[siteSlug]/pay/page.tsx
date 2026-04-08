import { PortalPay } from "@/components/portal/portal-pay";

export default async function Page({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalPay siteSlug={siteSlug} />;
}
