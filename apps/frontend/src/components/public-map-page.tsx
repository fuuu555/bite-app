"use client";

import { IconCurrentLocation, IconRefresh, IconSearch } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";

import {
  MapActiveFilterChips,
  MapFilterPopover,
  MapSearchBar,
  cloneMapFilters,
  countMapFilters,
  hasMapFilters,
} from "@/components/map-search-controls";
import { RestaurantPreviewCard } from "@/components/restaurant-preview-card";
import {
  defaultMapFilters,
  fetchPublicMapCuisines,
  fetchPublicMapSearch,
  fetchPublicMapRestaurants,
  type MapBounds,
  type MapCuisine,
  type MapFilters,
  type MapRestaurant,
  type MapSearchLocation,
} from "@/lib/public-map-api";

type MapLibreModule = typeof import("maplibre-gl");
type SavedViewport = { longitude: number; latitude: number; zoom: number };

const defaultViewport: SavedViewport = {
  longitude: 121.2258,
  latitude: 24.9537,
  zoom: 13,
};
const clusterDemoViewport: SavedViewport = {
  longitude: 121.2405,
  latitude: 24.9576,
  zoom: 13,
};
const viewportStorageKey = "bitemap-public-map-viewport";
const clusterDemoCuisine: MapCuisine = {
  id: "cluster-demo-cuisine",
  display_name: "群聚測試",
  color: "#d96c4f",
  icon_key: "tools-kitchen-3",
};
const clusterDemoOffsets = [
  [0, 0],
  [0.00035, 0.0002],
  [0.00055, -0.00025],
  [-0.00035, 0.00035],
  [-0.0006, -0.0002],
  [0.0008, 0.00055],
  [-0.00085, 0.00045],
  [0.0011, -0.00055],
  [-0.0012, -0.0005],
  [0.0001, -0.0011],
] as const;
const clusterDemoRestaurants: MapRestaurant[] = clusterDemoOffsets.map(
  ([longitudeOffset, latitudeOffset], index) => ({
    id: `cluster-demo-${index + 1}`,
    name: `中原群聚測試店家 ${index + 1}`,
    latitude: clusterDemoViewport.latitude + latitudeOffset,
    longitude: clusterDemoViewport.longitude + longitudeOffset,
    primary_cuisine: clusterDemoCuisine,
    price_range: "under_200",
    menu_url: null,
  }),
);

type ClusteredMapItem =
  | { kind: "restaurant"; restaurant: MapRestaurant; longitude: number; latitude: number }
  | {
      kind: "cluster";
      restaurants: MapRestaurant[];
      longitude: number;
      latitude: number;
    };

function isClusterDemoEnabled() {
  return (
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("cluster-demo") === "1"
  );
}

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
    west: Math.max(-180, bounds.getWest()),
    south: Math.max(-90, bounds.getSouth()),
    east: Math.min(180, bounds.getEast()),
    north: Math.min(90, bounds.getNorth()),
    zoom: map.getZoom(),
  };
}

function markerSizeForZoom(zoom: number) {
  const size = Math.round(Math.max(24, Math.min(42, 18 + zoom * 1.5)));
  return {
    size,
    fontSize: Math.max(11, Math.round(size * 0.34)),
  };
}

function updatePublicMapMarkerSizes(map: MapLibreMap) {
  map
    .getContainer()
    .querySelectorAll<HTMLElement>(".public-map-marker")
    .forEach((element) => updatePublicMapMarkerSizesForElement(element, map.getZoom()));
}

function updatePublicMapMarkerSizesForElement(element: HTMLElement, zoom: number) {
  const { size, fontSize } = markerSizeForZoom(zoom);
  const clusterBoost = element.classList.contains("public-map-cluster") ? 8 : 0;
  element.style.setProperty("--marker-size", `${Math.min(54, size + clusterBoost)}px`);
  element.style.setProperty(
    "--marker-font-size",
    `${Math.max(11, Math.round(fontSize + clusterBoost * 0.25))}px`,
  );
}

function clusterRestaurants(
  map: MapLibreMap,
  restaurants: MapRestaurant[],
  zoom: number,
  isDemo: boolean,
) {
  const radius = isDemo ? (zoom >= 15 ? 32 : 1_200) : zoom >= 16 ? 44 : 64;
  const clusters: Array<{
    restaurants: MapRestaurant[];
    longitude: number;
    latitude: number;
  }> = [];

  restaurants.forEach((restaurant) => {
    const point = map.project([restaurant.longitude, restaurant.latitude]);
    const existingCluster = clusters.find((cluster) => {
      const clusterPoint = map.project([cluster.longitude, cluster.latitude]);
      return Math.hypot(point.x - clusterPoint.x, point.y - clusterPoint.y) <= radius;
    });

    if (!existingCluster) {
      clusters.push({
        restaurants: [restaurant],
        longitude: restaurant.longitude,
        latitude: restaurant.latitude,
      });
      return;
    }

    existingCluster.restaurants.push(restaurant);
    existingCluster.longitude =
      existingCluster.restaurants.reduce((sum, item) => sum + item.longitude, 0) /
      existingCluster.restaurants.length;
    existingCluster.latitude =
      existingCluster.restaurants.reduce((sum, item) => sum + item.latitude, 0) /
      existingCluster.restaurants.length;
  });

  return clusters.map<ClusteredMapItem>((cluster) =>
    cluster.restaurants.length === 1
      ? {
          kind: "restaurant",
          restaurant: cluster.restaurants[0],
          longitude: cluster.longitude,
          latitude: cluster.latitude,
        }
      : { kind: "cluster", ...cluster },
  );
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
  const [mapZoom, setMapZoom] = useState(defaultViewport.zoom);
  const [message, setMessage] = useState("正在取得位置…");
  const [messageTone, setMessageTone] = useState<"neutral" | "error">("neutral");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Awaited<
    ReturnType<typeof fetchPublicMapSearch>
  > | null>(null);
  const [isSearchLoading, setIsSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [cuisines, setCuisines] = useState<Awaited<ReturnType<typeof fetchPublicMapCuisines>>>([]);
  const [isLoadingCuisines, setIsLoadingCuisines] = useState(false);
  const [activeFilters, setActiveFilters] = useState<MapFilters>(defaultMapFilters);
  const [pendingFilters, setPendingFilters] = useState<MapFilters>(defaultMapFilters);
  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;

  const searchMap = useCallback(async (map: MapLibreMap) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsSearching(true);
    setMessageTone("neutral");
    setMessage("正在搜尋這個區域…");
    try {
      if (isClusterDemoEnabled()) {
        setRestaurants(clusterDemoRestaurants);
        setSelectedRestaurant(null);
        setSearchNeeded(false);
        setMessage("群聚展示模式：中原附近 10 筆測試資料");
        return;
      }

      const response = await fetchPublicMapRestaurants(
        currentBounds(map),
        activeFiltersRef.current,
        controller.signal,
      );
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
          ? hasMapFilters(activeFiltersRef.current)
            ? "這個區域沒有符合條件的店家。"
            : "這個區域目前沒有已發布店家。"
          : `找到 ${response.restaurants.length} 間店家`,
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setSearchNeeded(true);
      setMessageTone("error");
      setMessage("店家資料載入失敗，原有結果已保留，請再試一次。");
    } finally {
      if (abortRef.current === controller) setIsSearching(false);
    }
  }, []);

  useEffect(() => {
    const query = searchQuery.trim();
    if (query.length < 2) return;

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setIsSearchLoading(true);
      void fetchPublicMapSearch(query, controller.signal)
        .then((response) => setSearchResults(response))
        .catch((error) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setSearchError("搜尋暫時無法使用，請稍後再試。");
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsSearchLoading(false);
        });
    }, 300);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [searchQuery]);

  useEffect(() => {
    if (!isFilterOpen || cuisines.length) return;
    const controller = new AbortController();
    void fetchPublicMapCuisines(controller.signal)
      .then((response) => setCuisines(response))
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setMessageTone("error");
        setMessage("料理分類載入失敗，請稍後再試。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingCuisines(false);
      });
    return () => controller.abort();
  }, [cuisines.length, isFilterOpen]);

  useEffect(() => {
    let disposed = false;

    async function initializeMap() {
      if (!containerRef.current) return;
      setMapStatus("loading");
      setMessageTone("neutral");
      setMessage("正在取得位置…");

      const savedViewport = readSavedViewport();
      const clusterDemo = isClusterDemoEnabled();
      let viewport = clusterDemo ? clusterDemoViewport : (savedViewport ?? defaultViewport);
      if (clusterDemo) {
        setMessage("群聚展示模式：中原附近 10 筆測試資料");
      } else {
        try {
          const position = await locateUser();
          viewport = {
            longitude: position.coords.longitude,
            latitude: position.coords.latitude,
            zoom: 14,
          };
          setMessage("已使用目前位置");
        } catch {
          setMessage(
            savedViewport ? "定位未開啟，已回到上次瀏覽位置。" : "定位未開啟，已顯示桃園中壢。",
          );
        }
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
        setMapZoom(map.getZoom());
        setMapStatus("ready");
        void searchMap(map);
        map.on("moveend", () => setSearchNeeded(true));
        map.on("zoom", () => updatePublicMapMarkerSizes(map));
        map.on("zoomend", () => setMapZoom(map.getZoom()));
      });
      map.on("click", () => {
        setSelectedRestaurant(null);
        setSearchResults(null);
        setIsFilterOpen(false);
      });
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
    const markerItems = clusterRestaurants(map, restaurants, mapZoom, isClusterDemoEnabled());
    markersRef.current = markerItems.map((item) => {
      const markerElement = document.createElement("button");
      markerElement.type = "button";
      if (item.kind === "cluster") {
        markerElement.className = "public-map-marker public-map-cluster";
        markerElement.textContent = String(item.restaurants.length);
        markerElement.setAttribute(
          "aria-label",
          `${item.restaurants.length} 間店家群聚，點擊放大地圖`,
        );
        markerElement.addEventListener("click", (event) => {
          event.stopPropagation();
          map.easeTo({
            center: [item.longitude, item.latitude],
            zoom: Math.min(map.getZoom() + 2, 18),
            duration: 350,
          });
        });
      } else {
        const markerLabel = document.createElement("span");
        markerElement.className = "public-map-marker";
        markerElement.style.setProperty("--marker-color", item.restaurant.primary_cuisine.color);
        markerLabel.textContent = item.restaurant.primary_cuisine.display_name.slice(0, 1);
        markerElement.append(markerLabel);
        markerElement.setAttribute(
          "aria-label",
          `${item.restaurant.name}，${item.restaurant.primary_cuisine.display_name}`,
        );
        markerElement.addEventListener("click", (event) => {
          event.stopPropagation();
          setSelectedRestaurant(item.restaurant);
        });
      }
      updatePublicMapMarkerSizesForElement(markerElement, map.getZoom());
      return new maplibregl.Marker({ element: markerElement, anchor: "bottom" })
        .setLngLat([item.longitude, item.latitude])
        .addTo(map);
    });
  }, [mapStatus, mapZoom, restaurants]);

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

  function handleSearchSubmit() {
    const location = searchResults?.locations[0];
    const restaurant = searchResults?.restaurants[0];
    if (location) {
      handleLocationSelect(location);
    } else if (restaurant) {
      handleRestaurantSelect(restaurant);
    }
  }

  function handleLocationSelect(location: MapSearchLocation) {
    const map = mapRef.current;
    if (!map) return;
    setSearchQuery("");
    setSearchResults(null);
    setSearchError(null);
    setIsFilterOpen(false);
    setSelectedRestaurant(null);
    map.easeTo({
      center: [location.longitude, location.latitude],
      zoom: Math.max(map.getZoom(), 14),
      duration: 500,
    });
    setSearchNeeded(true);
    setMessage("已定位到選取地區，請搜尋此區域。");
  }

  function handleRestaurantSelect(restaurant: MapRestaurant) {
    const map = mapRef.current;
    if (!map) return;
    setSearchQuery("");
    setSearchResults(null);
    setSearchError(null);
    setIsFilterOpen(false);
    setSelectedRestaurant(restaurant);
    map.easeTo({
      center: [restaurant.longitude, restaurant.latitude],
      zoom: Math.max(map.getZoom(), 16),
      duration: 500,
    });
  }

  function toggleFilterPopover() {
    const opening = !isFilterOpen;
    if (opening) {
      setPendingFilters(cloneMapFilters(activeFilters));
      if (!cuisines.length) setIsLoadingCuisines(true);
    }
    setSearchResults(null);
    setIsFilterOpen(opening);
  }

  function applyFilters() {
    const nextFilters = cloneMapFilters(pendingFilters);
    setActiveFilters(nextFilters);
    activeFiltersRef.current = nextFilters;
    setPendingFilters(cloneMapFilters(nextFilters));
    setIsFilterOpen(false);
    setSearchNeeded(true);
    setMessage("篩選條件已更新，請搜尋此區域。");
  }

  function removeFilter(key: "city" | "district" | "priceRange" | "cuisine", value?: string) {
    const nextFilters = cloneMapFilters(activeFilters);
    if (key === "city") {
      nextFilters.city = "";
      nextFilters.district = "";
    } else if (key === "district") {
      nextFilters.district = "";
    } else if (key === "priceRange" && value) {
      nextFilters.priceRanges = nextFilters.priceRanges.filter((item) => item !== value);
    } else if (key === "cuisine" && value) {
      nextFilters.cuisineIds = nextFilters.cuisineIds.filter((item) => item !== value);
    }
    setActiveFilters(nextFilters);
    activeFiltersRef.current = nextFilters;
    setPendingFilters(cloneMapFilters(nextFilters));
    setSearchNeeded(true);
    setMessage("篩選條件已更新，請搜尋此區域。");
  }

  return (
    <main className="public-map-page" aria-label="附近店家地圖">
      <div ref={containerRef} className="public-map-canvas" aria-label="公開店家地圖" />

      <div className="public-map-top-controls">
        <MapSearchBar
          query={searchQuery}
          results={searchResults}
          isSearching={isSearchLoading}
          error={searchError}
          isFilterOpen={isFilterOpen}
          activeFilterCount={countMapFilters(activeFilters)}
          onQueryChange={(query) => {
            setSearchQuery(query);
            setSearchResults(null);
            setSearchError(null);
            setIsSearchLoading(false);
          }}
          onSubmit={handleSearchSubmit}
          onClear={() => {
            setSearchQuery("");
            setSearchResults(null);
            setSearchError(null);
          }}
          onToggleFilters={toggleFilterPopover}
          onSelectLocation={handleLocationSelect}
          onSelectRestaurant={handleRestaurantSelect}
        />
        {isFilterOpen ? (
          <MapFilterPopover
            filters={pendingFilters}
            cuisines={cuisines}
            isLoadingCuisines={isLoadingCuisines}
            onChange={setPendingFilters}
            onClear={() => setPendingFilters(cloneMapFilters(defaultMapFilters))}
            onApply={applyFilters}
          />
        ) : null}
        <MapActiveFilterChips filters={activeFilters} cuisines={cuisines} onRemove={removeFilter} />
        {searchNeeded && mapStatus === "ready" && !selectedRestaurant && !isClusterDemoEnabled() ? (
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
      </div>

      <p
        className={`public-map-message${messageTone === "error" ? " is-error" : ""}`}
        role="status"
      >
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
