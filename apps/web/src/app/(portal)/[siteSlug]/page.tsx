import { PortalHome } from "@/components/portal/portal-home";

export default async function CaptivePortalPage({ params }: { params: Promise<{ siteSlug: string }> }) {
  const { siteSlug } = await params;
  return <PortalHome siteSlug={siteSlug} />;
}
