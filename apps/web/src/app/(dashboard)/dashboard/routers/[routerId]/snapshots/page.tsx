import { RouterSnapshots } from "@/components/routers/router-snapshots";

export default async function RouterSnapshotsPage({ params }: { params: Promise<{ routerId: string }> }) {
  const { routerId } = await params;
  return <RouterSnapshots routerId={routerId} />;
}
