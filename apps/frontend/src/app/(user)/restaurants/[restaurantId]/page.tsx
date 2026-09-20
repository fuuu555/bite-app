import { ComingSoon } from "@/components/coming-soon";

export default async function RestaurantPage({
  params,
}: {
  params: Promise<{ restaurantId: string }>;
}) {
  const { restaurantId } = await params;
  return (
    <ComingSoon
      title="餐廳詳細頁準備中"
      description="店家已從公開地圖正確選取，完整內容會在 Stage 4 加入。"
      backHref="/map"
      reference={restaurantId}
    />
  );
}
