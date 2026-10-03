"use client";

import {
  IconArrowLeft,
  IconArrowUp,
  IconArrowDown,
  IconCheck,
  IconMapPin,
  IconNavigation,
  IconRoute,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ItineraryMap, type ItineraryMapStop } from "@/features/itinerary/components/itinerary-map";
import {
  buildGoogleMapsDirectionsUrl,
  clearItinerary,
  emptyItinerary,
  getItineraryCategoryLabel,
  moveItineraryPlace,
  readSavedItinerary,
  removeItineraryPlace,
  writeSavedItinerary,
  type SavedItinerary,
  type SavedItineraryPlace,
} from "@/features/itinerary/lib/itinerary-storage";

const defaultCenter = { latitude: 24.9537, longitude: 121.2258 };

function mapRole(place: SavedItineraryPlace): ItineraryMapStop["role"] {
  if (place.category === "restaurant") return "meal";
  if (place.category === "hotel") return "lodging";
  if (place.category === "service_site") return "service_site";
  return "attraction";
}

function placeToMapStop(place: SavedItineraryPlace, index: number): ItineraryMapStop | null {
  if (place.latitude === null || place.longitude === null) return null;
  return {
    order: index + 1,
    role: mapRole(place),
    place: {
      latitude: place.latitude,
      longitude: place.longitude,
      icon_color: place.icon_color,
    },
  };
}

function distanceLabel(place: SavedItineraryPlace) {
  return place.latitude === null || place.longitude === null ? "缺少座標" : "可加入導航";
}

export function SavedItineraryPage() {
  const [itinerary, setItinerary] = useState<SavedItinerary>(emptyItinerary);
  const [isHydrated, setIsHydrated] = useState(false);
  const [clearPending, setClearPending] = useState(false);
  const [message, setMessage] = useState("");
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setItinerary(readSavedItinerary());
      setIsHydrated(true);
    });
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        ({ coords }) => setLocation({ latitude: coords.latitude, longitude: coords.longitude }),
        () => undefined,
        { enableHighAccuracy: false, maximumAge: 300_000, timeout: 8_000 },
      );
    }
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function persist(next: SavedItinerary, successMessage: string) {
    setItinerary(next);
    const saved = writeSavedItinerary(next);
    setMessage(saved ? successMessage : "行程已更新，但本次變更未保存。請稍後重試。");
  }

  function remove(place: SavedItineraryPlace) {
    persist(removeItineraryPlace(itinerary, place), `已移除「${place.name}」。`);
  }

  function move(fromIndex: number, toIndex: number) {
    persist(moveItineraryPlace(itinerary, fromIndex, toIndex), "行程順序已更新。");
  }

  function clear() {
    persist(clearItinerary(), "行程已清空。");
    setClearPending(false);
  }

  function startNavigation() {
    const url = buildGoogleMapsDirectionsUrl(itinerary.places, location);
    if (!url) {
      setMessage("目前沒有具備座標的地點，暫時無法開始導航。");
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const mapStops = useMemo(
    () =>
      itinerary.places
        .map(placeToMapStop)
        .filter((stop): stop is ItineraryMapStop => stop !== null),
    [itinerary.places],
  );
  const firstMappedPlace = mapStops[0]?.place;
  const center =
    location ??
    (firstMappedPlace
      ? { latitude: firstMappedPlace.latitude, longitude: firstMappedPlace.longitude }
      : defaultCenter);
  const hasNavigablePlace = mapStops.length > 0;

  return (
    <main className="saved-itinerary-page">
      <header className="saved-itinerary-header">
        <div>
          <Link className="saved-itinerary-back" href="/map">
            <IconArrowLeft aria-hidden="true" />
            回到地圖
          </Link>
          <span className="itinerary-eyebrow">
            <IconRoute aria-hidden="true" /> 我的行程
          </span>
          <h1>把想去的地方，排成一條走得通的路。</h1>
          <p>吃飯、景點、住宿都選好後，在這裡調整順序並開啟 Google Maps 導航。</p>
        </div>
        <div className="saved-itinerary-header__count">
          <strong>{isHydrated ? itinerary.places.length : "—"}</strong>
          <span>個地點</span>
        </div>
      </header>

      {message ? (
        <p className="saved-itinerary-message" role="status">
          <IconCheck aria-hidden="true" />
          {message}
          <button type="button" aria-label="關閉訊息" onClick={() => setMessage("")}>
            <IconX aria-hidden="true" />
          </button>
        </p>
      ) : null}

      {itinerary.places.length ? (
        <section className="saved-itinerary-layout" aria-label="我的旅遊行程">
          <div className="saved-itinerary-route">
            <div className="saved-itinerary-section-heading">
              <div>
                <span className="itinerary-eyebrow">ROUTE</span>
                <h2>今日行程</h2>
              </div>
              <button
                className="button button--quiet"
                type="button"
                onClick={() => setClearPending(true)}
              >
                <IconTrash aria-hidden="true" />
                清空
              </button>
            </div>

            {clearPending ? (
              <div className="saved-itinerary-confirm" role="alertdialog" aria-label="確認清空行程">
                <strong>要清空這份行程嗎？</strong>
                <span>清空後仍可回到地圖重新加入地點。</span>
                <div>
                  <button
                    className="button button--quiet"
                    type="button"
                    onClick={() => setClearPending(false)}
                  >
                    取消
                  </button>
                  <button className="button button--danger" type="button" onClick={clear}>
                    確認清空
                  </button>
                </div>
              </div>
            ) : null}

            <ol className="saved-itinerary-list">
              {itinerary.places.map((place, index) => (
                <li
                  key={`${place.source}-${place.source_record_id}`}
                  className="saved-itinerary-stop"
                >
                  <div className="saved-itinerary-stop__rail" aria-hidden="true">
                    <span>{index + 1}</span>
                    {index < itinerary.places.length - 1 ? <i /> : null}
                  </div>
                  <div className="saved-itinerary-stop__body">
                    <div className="saved-itinerary-stop__topline">
                      <span>{getItineraryCategoryLabel(place.category)}</span>
                      <small>{distanceLabel(place)}</small>
                    </div>
                    <h3>{place.name}</h3>
                    <p>{place.address ?? "官方資料未提供地址"}</p>
                    {place.latitude === null || place.longitude === null ? (
                      <small className="saved-itinerary-stop__warning">
                        <IconMapPin aria-hidden="true" /> 這個地點沒有座標，無法加入導航路線
                      </small>
                    ) : null}
                    <div className="saved-itinerary-stop__actions">
                      <button
                        type="button"
                        onClick={() => move(index, index - 1)}
                        disabled={index === 0}
                      >
                        <IconArrowUp aria-hidden="true" /> 上移
                      </button>
                      <button
                        type="button"
                        onClick={() => move(index, index + 1)}
                        disabled={index === itinerary.places.length - 1}
                      >
                        <IconArrowDown aria-hidden="true" /> 下移
                      </button>
                      <button type="button" onClick={() => remove(place)}>
                        <IconTrash aria-hidden="true" /> 移除
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <aside className="saved-itinerary-map-panel">
            <div className="saved-itinerary-map-panel__heading">
              <div>
                <span className="itinerary-eyebrow">MAP VIEW</span>
                <h2>路線預覽</h2>
              </div>
              <button
                className="button button--primary"
                type="button"
                onClick={startNavigation}
                disabled={!hasNavigablePlace}
              >
                <IconNavigation aria-hidden="true" />
                開始導航
              </button>
            </div>
            <ItineraryMap
              latitude={center.latitude}
              longitude={center.longitude}
              stops={mapStops}
            />
            <p className="saved-itinerary-map-panel__hint">
              {hasNavigablePlace
                ? "順序會帶入 Google Maps；目前位置會優先作為導航起點。"
                : "請先加入至少一個有座標的地點。"}
            </p>
          </aside>
        </section>
      ) : (
        <section className="saved-itinerary-empty">
          <IconRoute aria-hidden="true" />
          <h2>還沒有行程地點</h2>
          <p>回到地圖，從餐廳、景點或住宿的預覽卡加入第一站。</p>
          <Link className="button button--primary" href="/map">
            <IconMapPin aria-hidden="true" />
            前往地圖探索
          </Link>
        </section>
      )}
    </main>
  );
}
