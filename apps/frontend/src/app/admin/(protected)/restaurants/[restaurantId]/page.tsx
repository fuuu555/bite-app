import { RestaurantEditor } from "@/components/restaurant-editor";

export default async function EditRestaurantPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId } = await params;
  return <RestaurantEditor restaurantId={restaurantId} />;
}
