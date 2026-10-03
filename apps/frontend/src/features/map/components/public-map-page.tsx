"use client";

import { IconCurrentLocation, IconRefresh } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapGeoJSONFeature,
  MapMouseEvent,
} from "maplibre-gl";

import {
  MapActiveFilterChips,
  MapFilterPopover,
  MapSearchBar,
  cloneMapFilters,
  countMapFilters,
  hasMapFilters,
} from "@/features/map/components/map-search-controls";
import { RestaurantPreviewCard } from "@/features/map/components/restaurant-preview-card";
import {
  defaultMapFilters,
  fetchPublicMapCuisines,
  fetchPublicMapSearch,
  fetchPublicMapRestaurants,
  type MapBounds,
  type MapCuisine,
  type MapFilters,
  type MapRestaurant,
} from "@/features/map/api/public-map-api";

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
const restaurantSourceId = "public-map-restaurants";
const clusterLayerId = "public-map-clusters";
const clusterCountLayerId = "public-map-cluster-count";
const restaurantLayerId = "public-map-restaurants-unclustered";
const restaurantLabelLayerId = "public-map-restaurant-label";
type RestaurantFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: RestaurantFeatureProperties;
  }>;
};

const emptyFeatureCollection: RestaurantFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};
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
    photo_url: null,
  }),
);

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

type RestaurantFeatureProperties = {
  restaurant_id: string;
  cuisine_color: string;
  cuisine_initial: string;
  is_selected: boolean;
};

function restaurantFeatureCollection(
  restaurants: MapRestaurant[],
  selectedRestaurantId: string | null,
): RestaurantFeatureCollection {
  return {
    type: "FeatureCollection",
    features: restaurants.map((restaurant) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [restaurant.longitude, restaurant.latitude],
      },
      properties: {
        restaurant_id: restaurant.id,
        cuisine_color: restaurant.primary_cuisine.color,
        cuisine_initial: restaurant.primary_cuisine.display_name.slice(0, 1),
        is_selected: restaurant.id === selectedRestaurantId,
      },
    })),
  };
}

function addRestaurantSourceAndLayers(map: MapLibreMap) {
  if (map.getSource(restaurantSourceId)) return;

  map.addSource(restaurantSourceId, {
    type: "geojson",
    data: emptyFeatureCollection,
    cluster: true,
    clusterMaxZoom: 15,
    clusterRadius: 52,
  });
  map.addLayer({
    id: clusterLayerId,
    type: "circle",
    source: restaurantSourceId,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": [
        "step",
        ["get", "point_count"],
        "#4e8f6b",
        10,
        "#3d7c61",
        50,
        "#2d624e",
      ],
      "circle-radius": ["step", ["get", "point_count"], 20, 10, 24, 50, 29],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: clusterCountLayerId,
    type: "symbol",
    source: restaurantSourceId,
    filter: ["has", "point_count"],
    layout: {
      "text-field": [
        "case",
        [">", ["get", "point_count"], 100],
        "100+",
        ["to-string", ["get", "point_count"]],
      ],
      "text-size": 13,
      "text-font": ["Open Sans Bold"],
    },
    paint: { "text-color": "#ffffff" },
  });
  map.addLayer({
    id: restaurantLayerId,
    type: "circle",
    source: restaurantSourceId,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": ["get", "cuisine_color"],
      "circle-radius": ["case", ["get", "is_selected"], 12, 10],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: restaurantLabelLayerId,
    type: "symbol",
    source: restaurantSourceId,
    filter: ["!", ["has", "point_count"]],
    layout: {
      "text-field": ["get", "cuisine_initial"],
      "text-size": 11,
      "text-allow-overlap": true,
    },
    paint: { "text-color": "#ffffff" },
  });
}

function sourceFromMap(map: MapLibreMap) {
  return map.getSource(restaurantSourceId) as GeoJSONSource | undefined;
}

function featureAtMapPoint(map: MapLibreMap, event: MapMouseEvent) {
  return map.queryRenderedFeatures(event.point, {
    layers: [clusterLayerId, clusterCountLayerId, restaurantLayerId],
  })[0] as MapGeoJSONFeature | undefined;
}

export function PublicMapPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error">("loading");
  const [restaurants, setRestaurants] = useState<MapRestaurant[]>([]);
  const restaurantsRef = useRef<MapRestaurant[]>([]);
  restaurantsRef.current = restaurants;
  const [selectedRestaurant, setSelectedRestaurant] = useState<MapRestaurant | null>(null);
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
  // The stable search callback reads current filters without rebuilding the MapLibre instance.
  // 穩定的搜尋 callback 透過 ref 讀取最新篩選，避免重建 MapLibre 實例。
  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;

  const searchMap = useCallback(async (map: MapLibreMap) => {
    // Only the newest viewport request may update results; failures intentionally keep existing markers.
    // 只允許最新地圖範圍請求更新結果；失敗時刻意保留原有標記。
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setMessageTone("neutral");
    setMessage("正在搜尋這個區域…");
    try {
      if (isClusterDemoEnabled()) {
        setRestaurants(clusterDemoRestaurants);
        setSelectedRestaurant(null);
        setMessage("群聚展示模式：中原附近 10 筆測試資料");
        return;
      }

      const response = await fetchPublicMapRestaurants(
        currentBounds(map),
        activeFiltersRef.current,
        controller.signal,
      );
      if (response.status === "zoom_required") {
        setRestaurants(response.restaurants);
        setSelectedRestaurant(null);
        setMessage("範圍較大，先顯示部分店家；放大地圖可查看更完整的群聚。");
        return;
      }
      setRestaurants(response.restaurants);
      setSelectedRestaurant(null);
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
      setMessageTone("error");
      setMessage("店家資料載入失敗，原有結果已保留；移動地圖後會自動重試。");
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
    let moveSearchTimer: number | null = null;

    async function initializeMap() {
      if (!containerRef.current) return;
      setMapStatus("loading");
      setMessageTone("neutral");
      setMessage("正在準備地圖…");

      const savedViewport = readSavedViewport();
      const clusterDemo = isClusterDemoEnabled();
      const viewport = clusterDemo ? clusterDemoViewport : (savedViewport ?? defaultViewport);
      const locationPromise = clusterDemo
        ? Promise.resolve<GeolocationPosition | null>(null)
        : locateUser().catch(() => null);

      if (clusterDemo) {
        setMessage("群聚展示模式：中原附近 10 筆測試資料");
      }

      const maplibregl = await import("maplibre-gl");
      if (disposed || !containerRef.current) return;
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      let mapReady = false;
      let userMoved = false;
      let pendingPosition: GeolocationPosition | null = null;

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
      const applyLocation = (position: GeolocationPosition) => {
        // A late geolocation result must not pull the map away after the user has started navigating.
        // 定位延遲回傳時，若使用者已操作地圖就不能再把畫面拉回目前位置。
        if (disposed || !mapReady || userMoved) return;
        map.easeTo({
          center: [position.coords.longitude, position.coords.latitude],
          zoom: 14,
          duration: 350,
        });
        setMessage("已使用目前位置");
      };
      void locationPromise.then((position) => {
        if (disposed) return;
        if (position) {
          pendingPosition = position;
          applyLocation(position);
          return;
        }
        if (!clusterDemo) {
          setMessage(
            savedViewport ? "定位未開啟，已回到上次瀏覽位置。" : "定位未開啟，已顯示桃園中壢。",
          );
        }
      });
      map.on("movestart", () => {
        if (mapReady) userMoved = true;
      });
      map.once("load", () => {
        if (disposed) return;
        mapReady = true;
        addRestaurantSourceAndLayers(map);
        if (pendingPosition) applyLocation(pendingPosition);
        setMapStatus("ready");
        void searchMap(map);
        map.on("moveend", () => {
          if (moveSearchTimer !== null) window.clearTimeout(moveSearchTimer);
          moveSearchTimer = window.setTimeout(() => {
            if (!disposed) void searchMap(map);
          }, 450);
        });
      });
      map.on("click", async (event) => {
        const feature = featureAtMapPoint(map, event);
        if (!feature) {
          setSelectedRestaurant(null);
          setSearchResults(null);
          setIsFilterOpen(false);
          return;
        }

        if (feature.properties?.cluster_id !== undefined) {
          const source = sourceFromMap(map);
          if (!source) return;
          const clusterId = Number(feature.properties.cluster_id);
          const expansionZoom = await source.getClusterExpansionZoom(clusterId);
          if (disposed || feature.geometry.type !== "Point") return;
          map.easeTo({
            center: feature.geometry.coordinates as [number, number],
            zoom: Math.min(expansionZoom, 18),
            duration: 350,
          });
          return;
        }

        const restaurantId = String(feature.properties?.restaurant_id ?? "");
        const restaurant = restaurantsRef.current.find((item) => item.id === restaurantId);
        if (restaurant) setSelectedRestaurant(restaurant);
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
      // MapLibre owns DOM nodes and listeners outside React, so dispose every imperative resource.
      // MapLibre 在 React 外管理 DOM 與事件，因此卸載時需完整釋放命令式資源。
      disposed = true;
      if (moveSearchTimer !== null) window.clearTimeout(moveSearchTimer);
      abortRef.current?.abort();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [retryKey, searchMap]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map ? sourceFromMap(map) : undefined;
    if (!source || mapStatus !== "ready") return;
    source.setData(restaurantFeatureCollection(restaurants, selectedRestaurant?.id ?? null));
  }, [mapStatus, restaurants, selectedRestaurant]);

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
      setMessage("位置已更新，正在更新店家。");
    } catch {
      setMessageTone("error");
      setMessage("無法取得目前位置，請確認瀏覽器定位權限。");
    }
  }

  function handleSearchSubmit() {
    const restaurant = searchResults?.restaurants[0];
    if (restaurant) {
      handleRestaurantSelect(restaurant);
    }
  }

  function handleRestaurantSelect(restaurant: MapRestaurant) {
    const map = mapRef.current;
    if (!map) return;
    setRestaurants((current) => {
      const existing = current.some((item) => item.id === restaurant.id);
      return existing ? current : [...current, restaurant];
    });
    setSearchQuery("");
    setSearchResults(null);
    setSearchError(null);
    setIsFilterOpen(false);
    setSelectedRestaurant(restaurant);
    setMessageTone("neutral");
    setMessage("已標示搜尋店家，正在載入周邊店家。");
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
    setMessage("篩選條件已更新，正在重新載入店家。");
    if (mapRef.current && mapStatus === "ready") void searchMap(mapRef.current);
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
    setMessage("篩選條件已更新，正在重新載入店家。");
    if (mapRef.current && mapStatus === "ready") void searchMap(mapRef.current);
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
