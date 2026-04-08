import { RouterOverview } from "@/components/routers/router-overview";

export default async function RouterDetailPage({ params }: { params: Promise<{ routerId: string }> }) {
  const { routerId } = await params;
  return <RouterOverview routerId={routerId} />;
}
