import { PortalLayoutClient } from "@/components/portal/portal-layout-client";
import { getApiBaseUrl } from "@/lib/config";
import type { PortalSiteHealth } from "@/lib/portal/site-health";

type BJson = {
  success?: boolean;
  data?: {
    site?: { name?: string; slug?: string };
    branding?: {
      primary_color?: string | null;
      welcome_message?: string | null;
    } | null;
  };
};

export default async function SitePortalLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ siteSlug: string }>;
}) {
  const { siteSlug } = await params;
  const base = getApiBaseUrl();
  let siteName = siteSlug;
  let accent = "#FBA002";
  let welcome: string | null = null;
  let siteHealth: PortalSiteHealth = "ok";

  const url = `${base.replace(/\/$/, "")}/api/v1/portal/${encodeURIComponent(siteSlug)}/branding`;

  try {
    const res = await fetch(url, { next: { revalidate: 60 } });
    if (res.status === 404) {
      siteHealth = "missing";
    } else if (!res.ok) {
      siteHealth = "degraded";
    } else {
      const text = await res.text();
      let json: BJson = {};
      try {
        json = text ? (JSON.parse(text) as BJson) : {};
      } catch {
        siteHealth = "degraded";
      }
      if (siteHealth === "ok" && json.success && json.data?.site?.name) siteName = json.data.site.name;
      const b = json.data?.branding;
      if (siteHealth === "ok" && b?.primary_color) accent = b.primary_color;
      if (siteHealth === "ok" && b?.welcome_message) welcome = b.welcome_message;
    }
  } catch {
    siteHealth = "degraded";
  }

  return (
    <PortalLayoutClient siteSlug={siteSlug} siteName={siteName} accent={accent} welcome={welcome} siteHealth={siteHealth}>
      {children}
    </PortalLayoutClient>
  );
}
