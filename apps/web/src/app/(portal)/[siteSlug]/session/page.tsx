import { PortalSessionStatus } from "@/components/portal/portal-session";

export default async function Page({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalSessionStatus siteSlug={siteSlug} />;
}
