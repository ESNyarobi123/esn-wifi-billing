import { PortalPlans } from "@/components/portal/portal-plans";

export default async function Page({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalPlans siteSlug={siteSlug} />;
}
