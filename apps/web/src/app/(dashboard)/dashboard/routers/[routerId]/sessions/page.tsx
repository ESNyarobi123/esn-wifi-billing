import { RouterLiveSessions } from "@/components/routers/router-live-sessions";

export default async function RouterSessionsPage({ params }: { params: Promise<{ routerId: string }> }) {
  const { routerId } = await params;
  return <RouterLiveSessions routerId={routerId} />;
}
