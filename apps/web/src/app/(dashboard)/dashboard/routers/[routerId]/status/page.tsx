import { RouterStatusView } from "@/components/routers/router-status-view";

export default async function RouterStatusPage({ params }: { params: Promise<{ routerId: string }> }) {
  const { routerId } = await params;
  return <RouterStatusView routerId={routerId} />;
}
