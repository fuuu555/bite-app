import { MealsPage } from "@/components/user/meals-page";

export default async function MealsRoute({
  searchParams,
}: {
  searchParams: Promise<{ restaurantId?: string; compose?: string; cancelled?: string }>;
}) {
  const { restaurantId, compose, cancelled } = await searchParams;
  return (
    <MealsPage
      initialRestaurantId={restaurantId}
      compose={compose === "1"}
      cancelled={cancelled === "host" ? "host" : cancelled === "1" ? "self" : null}
    />
  );
}
