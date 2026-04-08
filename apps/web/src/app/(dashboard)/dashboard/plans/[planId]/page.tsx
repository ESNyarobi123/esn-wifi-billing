import { PlanEditForm } from "@/components/plans/plan-edit-form";

export default async function EditPlanPage({ params }: { params: Promise<{ planId: string }> }) {
  const { planId } = await params;
  return <PlanEditForm planId={planId} />;
}
