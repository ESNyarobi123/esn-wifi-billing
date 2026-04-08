import { PortalAccess } from "@/components/portal/portal-access";

export default async function Page({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalAccess siteSlug={siteSlug} />;
}
