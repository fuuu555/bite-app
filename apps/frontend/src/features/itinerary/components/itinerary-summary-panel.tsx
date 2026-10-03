import { IconArrowRight, IconRoute, IconX } from "@tabler/icons-react";
import Link from "next/link";

import {
  getItineraryCategoryLabel,
  type SavedItinerary,
  type SavedItineraryPlace,
} from "@/features/itinerary/lib/itinerary-storage";

type ItinerarySummaryPanelProps = {
  itinerary: SavedItinerary;
  onRemove?: (place: SavedItineraryPlace) => void;
};

export function ItinerarySummaryPanel({ itinerary, onRemove }: ItinerarySummaryPanelProps) {
  return (
    <aside className="itinerary-map-summary" aria-label="我的行程摘要">
      <div className="itinerary-map-summary__heading">
        <div>
          <span className="itinerary-map-summary__eyebrow">
            <IconRoute aria-hidden="true" /> 我的行程
          </span>
          <strong>{itinerary.places.length} 個地點</strong>
        </div>
        <Link href="/itinerary" aria-label="查看完整行程">
          <IconArrowRight aria-hidden="true" />
        </Link>
      </div>
      {itinerary.places.length ? (
        <ol className="itinerary-map-summary__list">
          {itinerary.places.slice(0, 4).map((place, index) => (
            <li key={`${place.source}-${place.source_record_id}`}>
              <span className="itinerary-map-summary__number">{index + 1}</span>
              <span>
                <small>{getItineraryCategoryLabel(place.category)}</small>
                <strong>{place.name}</strong>
              </span>
              {onRemove ? (
                <button
                  type="button"
                  onClick={() => onRemove(place)}
                  aria-label={`移除 ${place.name}`}
                >
                  <IconX aria-hidden="true" />
                </button>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="itinerary-map-summary__empty">在地圖選一個餐廳、景點或住宿加入行程。</p>
      )}
      <Link className="button button--primary itinerary-map-summary__link" href="/itinerary">
        查看完整行程
        <IconArrowRight aria-hidden="true" />
      </Link>
    </aside>
  );
}
