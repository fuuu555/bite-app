import { IconArrowRight, IconToolsKitchen3, IconX } from "@tabler/icons-react";
import Link from "next/link";

import { type MapRestaurant, priceRangeLabels } from "@/lib/public-map-api";

type RestaurantPreviewCardProps = {
  restaurant: MapRestaurant;
  onClose: () => void;
};

export function RestaurantPreviewCard({ restaurant, onClose }: RestaurantPreviewCardProps) {
  return (
    <article className="restaurant-preview" aria-labelledby="restaurant-preview-title">
      <button
        className="restaurant-preview__close"
        type="button"
        onClick={onClose}
        aria-label="關閉店家預覽"
      >
        <IconX aria-hidden="true" />
      </button>
      <div
        className="restaurant-preview__cuisine"
        style={{ "--cuisine-color": restaurant.primary_cuisine.color } as React.CSSProperties}
      >
        <IconToolsKitchen3 aria-hidden="true" />
        {restaurant.primary_cuisine.display_name}
      </div>
      <h2 id="restaurant-preview-title">{restaurant.name}</h2>
      <p>{priceRangeLabels[restaurant.price_range]}</p>
      <Link href={`/restaurants/${restaurant.id}`}>
        查看餐廳
        <IconArrowRight aria-hidden="true" />
      </Link>
    </article>
  );
}
