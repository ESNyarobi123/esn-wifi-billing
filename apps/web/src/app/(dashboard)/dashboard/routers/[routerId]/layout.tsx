import { RouterSubnav } from "@/components/routers/router-subnav";

export default async function RouterSegmentLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ routerId: string }>;
}) {
  const { routerId } = await params;
  return (
    <div>
      <RouterSubnav routerId={routerId} />
      {children}
    </div>
  );
}
