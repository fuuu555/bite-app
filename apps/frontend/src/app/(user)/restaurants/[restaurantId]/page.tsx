import { RestaurantDetailPage } from "@/components/user/restaurant-detail-page";

export default async function RestaurantPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId } = await params;
  return <RestaurantDetailPage restaurantId={restaurantId} />;
}
