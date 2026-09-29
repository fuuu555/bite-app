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
      {restaurant.photo_url ? (
        <div className="restaurant-preview__photo">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={restaurant.photo_url} alt={`${restaurant.name}店家照片`} />
        </div>
      ) : null}
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
