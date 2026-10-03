"use client";

import { IconArrowRight, IconRoute, IconX } from "@tabler/icons-react";
import Link from "next/link";

import {
  getItineraryCategoryLabel,
  type SavedItinerary,
  type SavedItineraryPlace,
} from "@/features/itinerary/lib/itinerary-storage";

type ItineraryDraftPanelProps = {
  itinerary: SavedItinerary;
  canShowRoute: boolean;
  routeIsVisible: boolean;
  expanded: boolean;
  onToggleExpanded: () => void;
  onShowRoute: () => void;
  onRemove: (place: SavedItineraryPlace) => void;
};

export function ItineraryDraftPanel({
  itinerary,
  canShowRoute,
  routeIsVisible,
  expanded,
  onToggleExpanded,
  onShowRoute,
  onRemove,
}: ItineraryDraftPanelProps) {
  const count = itinerary.places.length;

  return (
    <aside className={`itinerary-draft${expanded ? " is-expanded" : ""}`} aria-label="我的行程草稿">
      <div className="itinerary-draft__header">
        <div>
          <span className="itinerary-eyebrow">
            <IconRoute aria-hidden="true" /> 我的行程草稿
          </span>
          <h2>{count ? `已加入 ${count} 個地點` : "先收藏想去的地方"}</h2>
        </div>
        <button
          className="itinerary-draft__expand"
          type="button"
          onClick={onToggleExpanded}
          aria-expanded={expanded}
          aria-label={expanded ? "收合行程草稿" : "展開行程草稿"}
        >
          {expanded ? "收合" : "查看"}
        </button>
      </div>

      {count ? (
        <ol className="itinerary-draft__list">
          {itinerary.places.map((place, index) => (
            <li key={`${place.source}-${place.source_record_id}`}>
              <span className="itinerary-draft__number">{index + 1}</span>
              <span className="itinerary-draft__place">
                <small>{getItineraryCategoryLabel(place.category)}</small>
                <strong title={place.name}>{place.name}</strong>
              </span>
              <button
                type="button"
                onClick={() => onRemove(place)}
                aria-label={`從行程草稿移除 ${place.name}`}
              >
                <IconX aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="itinerary-draft__empty">從推薦地點加入餐廳、景點或住宿。</p>
      )}

      <div className="itinerary-draft__actions">
        <button
          className="button button--primary"
          type="button"
          onClick={onShowRoute}
          disabled={!canShowRoute}
          aria-pressed={routeIsVisible}
        >
          <IconRoute aria-hidden="true" />
          {routeIsVisible ? "更新地圖路線" : "在地圖顯示路線"}
        </button>
        {!canShowRoute ? <small>至少加入 2 個有座標的地點即可顯示路線。</small> : null}
        <Link href="/itinerary">
          管理完整行程 <IconArrowRight aria-hidden="true" />
        </Link>
      </div>
    </aside>
  );
}
