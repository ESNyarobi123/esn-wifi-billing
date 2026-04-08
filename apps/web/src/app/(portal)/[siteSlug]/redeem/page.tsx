import { PortalRedeem } from "@/components/portal/portal-redeem";

export default async function Page({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalRedeem siteSlug={siteSlug} />;
}
