import { MealDetailPage } from "@/components/user/meal-detail-page";

export default async function MealDetailRoute({ params }: { params: Promise<{ mealId: string }> }) {
  const { mealId } = await params;
  return <MealDetailPage mealId={mealId} />;
}
