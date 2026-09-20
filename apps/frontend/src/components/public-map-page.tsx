"use client";

import { IconCurrentLocation, IconRefresh, IconSearch } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";

import { RestaurantPreviewCard } from "@/components/restaurant-preview-card";
import {
  fetchPublicMapRestaurants,
  type MapBounds,
  type MapRestaurant,
} from "@/lib/public-map-api";

type MapLibreModule = typeof import("maplibre-gl");
type SavedViewport = { longitude: number; latitude: number; zoom: number };

const defaultViewport: SavedViewport = {
  longitude: 121.2258,
  latitude: 24.9537,
  zoom: 13,
};
const viewportStorageKey = "bitemap-public-map-viewport";

function readSavedViewport(): SavedViewport | null {
  try {
    const value = window.localStorage.getItem(viewportStorageKey);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<SavedViewport>;
    if (
      typeof parsed.longitude !== "number" ||
      typeof parsed.latitude !== "number" ||
      typeof parsed.zoom !== "number"
    ) {
      return null;
    }
    return parsed as SavedViewport;
  } catch {
    return null;
  }
}

function locateUser(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("geolocation unavailable"));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      maximumAge: 120_000,
      timeout: 5_000,
    });
  });
}

function currentBounds(map: MapLibreMap): MapBounds {
  const bounds = map.getBounds();
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
    zoom: map.getZoom(),
  };
}

export function PublicMapPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const maplibreRef = useRef<MapLibreModule | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error">("loading");
  const [restaurants, setRestaurants] = useState<MapRestaurant[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState<MapRestaurant | null>(null);
  const [searchNeeded, setSearchNeeded] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [message, setMessage] = useState("正在取得位置…");
  const [messageTone, setMessageTone] = useState<"neutral" | "error">("neutral");

  const searchMap = useCallback(async (map: MapLibreMap) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsSearching(true);
    setMessageTone("neutral");
    setMessage("正在搜尋這個區域…");
    try {
      const response = await fetchPublicMapRestaurants(currentBounds(map), controller.signal);
      if (response.status === "zoom_required") {
        setMessage("這個範圍的店家太多，請放大地圖後再搜尋。");
        return;
      }
      setRestaurants(response.restaurants);
      setSelectedRestaurant(null);
      setSearchNeeded(false);
      const center = map.getCenter();
      window.localStorage.setItem(
        viewportStorageKey,
        JSON.stringify({ longitude: center.lng, latitude: center.lat, zoom: map.getZoom() }),
      );
      setMessage(
        response.restaurants.length === 0
          ? "這個區域目前沒有已發布店家。"
          : `找到 ${response.restaurants.length} 間店家`,
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMessageTone("error");
      setMessage("店家資料載入失敗，原有結果已保留，請再試一次。");
    } finally {
      if (abortRef.current === controller) setIsSearching(false);
    }
  }, []);

  useEffect(() => {
    let disposed = false;

    async function initializeMap() {
      if (!containerRef.current) return;
      setMapStatus("loading");
      setMessageTone("neutral");
      setMessage("正在取得位置…");

      const savedViewport = readSavedViewport();
      let viewport = savedViewport ?? defaultViewport;
      try {
        const position = await locateUser();
        viewport = {
          longitude: position.coords.longitude,
          latitude: position.coords.latitude,
          zoom: 14,
        };
        setMessage("已使用目前位置");
      } catch {
        setMessage(savedViewport ? "定位未開啟，已回到上次瀏覽位置。" : "定位未開啟，已顯示桃園中壢。");
      }

      const maplibregl = await import("maplibre-gl");
      if (disposed || !containerRef.current) return;
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      maplibreRef.current = maplibregl;

      const map = new maplibregl.Map({
        container: containerRef.current,
        style:
          process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/positron",
        center: [viewport.longitude, viewport.latitude],
        zoom: viewport.zoom,
        pitch: 0,
        bearing: 0,
        maxPitch: 0,
        dragRotate: false,
        touchPitch: false,
        attributionControl: { compact: true },
      });
      mapRef.current = map;
      map.once("load", () => {
        if (disposed) return;
        setMapStatus("ready");
        void searchMap(map);
        map.on("moveend", () => setSearchNeeded(true));
      });
      map.on("click", () => setSelectedRestaurant(null));
      map.on("error", () => {
        if (!map.loaded()) {
          setMapStatus("error");
          setMessageTone("error");
          setMessage("地圖底圖載入失敗，請檢查網路後重試。");
        }
      });
    }

    void initializeMap();
    return () => {
      disposed = true;
      abortRef.current?.abort();
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
      maplibreRef.current = null;
    };
  }, [retryKey, searchMap]);

  useEffect(() => {
    const map = mapRef.current;
    const maplibregl = maplibreRef.current;
    if (!map || !maplibregl || mapStatus !== "ready") return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = restaurants.map((restaurant) => {
      const markerElement = document.createElement("button");
      const markerLabel = document.createElement("span");
      markerElement.type = "button";
      markerElement.className = "public-map-marker";
      markerElement.style.setProperty("--marker-color", restaurant.primary_cuisine.color);
      markerLabel.textContent = restaurant.primary_cuisine.display_name.slice(0, 1);
      markerElement.append(markerLabel);
      markerElement.setAttribute(
        "aria-label",
        `${restaurant.name}，${restaurant.primary_cuisine.display_name}`,
      );
      markerElement.addEventListener("click", (event) => {
        event.stopPropagation();
        setSelectedRestaurant(restaurant);
      });
      return new maplibregl.Marker({ element: markerElement, anchor: "bottom" })
        .setLngLat([restaurant.longitude, restaurant.latitude])
        .addTo(map);
    });
  }, [mapStatus, restaurants]);

  async function returnToCurrentLocation() {
    const map = mapRef.current;
    if (!map) return;
    setMessageTone("neutral");
    setMessage("正在取得目前位置…");
    try {
      const position = await locateUser();
      map.easeTo({
        center: [position.coords.longitude, position.coords.latitude],
        zoom: Math.max(map.getZoom(), 14),
        duration: 500,
      });
      setMessage("位置已更新，請搜尋此區域。");
    } catch {
      setMessageTone("error");
      setMessage("無法取得目前位置，請確認瀏覽器定位權限。");
    }
  }

  return (
    <main className="public-map-page" aria-label="附近店家地圖">
      <div ref={containerRef} className="public-map-canvas" aria-label="公開店家地圖" />

      <div className="public-map-brand">
        <span aria-hidden="true">B</span>
        <div>
          <strong>BiteMap</strong>
          <small>附近店家</small>
        </div>
      </div>

      {searchNeeded && mapStatus === "ready" ? (
        <button
          className="map-search-area"
          type="button"
          onClick={() => mapRef.current && void searchMap(mapRef.current)}
          disabled={isSearching}
        >
          <IconSearch aria-hidden="true" />
          {isSearching ? "搜尋中…" : "搜尋此區域"}
        </button>
      ) : null}

      <p className={`public-map-message${messageTone === "error" ? " is-error" : ""}`} role="status">
        {message}
      </p>

      {mapStatus === "loading" ? (
        <div className="public-map-loading" aria-live="polite">
          <span />
          正在準備地圖…
        </div>
      ) : null}

      {mapStatus === "error" ? (
        <div className="public-map-error" role="alert">
          <strong>地圖暫時無法載入</strong>
          <p>請確認網路連線後再試一次。</p>
          <button type="button" onClick={() => setRetryKey((value) => value + 1)}>
            <IconRefresh aria-hidden="true" />
            重新載入
          </button>
        </div>
      ) : null}

      <button
        className="map-location-control"
        type="button"
        onClick={() => void returnToCurrentLocation()}
        disabled={mapStatus !== "ready"}
        aria-label="回到我的位置"
      >
        <IconCurrentLocation aria-hidden="true" />
      </button>

      {selectedRestaurant ? (
        <RestaurantPreviewCard
          restaurant={selectedRestaurant}
          onClose={() => setSelectedRestaurant(null)}
        />
      ) : null}
    </main>
  );
}
