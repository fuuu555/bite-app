import { IconCheck, IconMapPin, IconPlus, IconX } from "@tabler/icons-react";

import type { TourismPlace } from "@/features/map/api/public-map-api";

type TourismPreviewCardProps = {
  place: TourismPlace;
  isInItinerary: boolean;
  onAddToItinerary: () => void;
  onClose: () => void;
};

const categoryLabels: Record<TourismPlace["category"], string> = {
  restaurant: "觀光署餐飲資料",
  attraction: "觀光署景點資料",
  hotel: "觀光署旅宿資料",
  service_site: "觀光署旅遊服務站",
};

export function TourismPreviewCard({ place, isInItinerary, onAddToItinerary, onClose }: TourismPreviewCardProps) {
  return (
    <article className="tourism-preview" aria-labelledby="tourism-preview-title">
      <button
        className="restaurant-preview__close"
        type="button"
        onClick={onClose}
        aria-label="關閉官方觀光資料預覽"
      >
        <IconX aria-hidden="true" />
      </button>
      <div className="tourism-preview__source">
        <IconMapPin aria-hidden="true" />
        {categoryLabels[place.category]}
      </div>
      <h2 id="tourism-preview-title">{place.name}</h2>
      <p>{place.address ?? "官方資料未提供地址"}</p>
      {place.opening_hours ? <p>{place.opening_hours}</p> : null}
      <div className="tourism-preview__meta">
        <span>政府開放資料</span>
        {place.source_updated_at ? (
          <span>更新於 {new Date(place.source_updated_at).toLocaleDateString("zh-TW")}</span>
        ) : null}
      </div>
      <button
        className={`button ${isInItinerary ? "button--secondary" : "button--primary"} map-preview__itinerary-action`}
        type="button"
        onClick={onAddToItinerary}
        disabled={isInItinerary}
      >
        {isInItinerary ? <IconCheck aria-hidden="true" /> : <IconPlus aria-hidden="true" />}
        {isInItinerary ? "已加入行程" : "加入行程"}
      </button>
      {place.official_url ? (
        <a href={place.official_url} target="_blank" rel="noreferrer">
          查看官方網站
        </a>
      ) : null}
    </article>
  );
}
