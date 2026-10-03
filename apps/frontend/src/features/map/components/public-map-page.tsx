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
import { TourismPreviewCard } from "@/features/map/components/tourism-preview-card";
import {
  defaultMapFilters,
  fetchPublicMapCuisines,
  fetchPublicMapSearch,
  fetchPublicMapRestaurants,
  fetchPublicTourismPlaces,
  type MapBounds,
  type MapCuisine,
  type MapFilters,
  type MapRestaurant,
  type TourismPlace,
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
const tourismSourceId = "public-map-tourism";
const tourismClusterLayerId = "public-map-tourism-clusters";
const tourismClusterCountLayerId = "public-map-tourism-cluster-count";
const tourismLayerId = "public-map-tourism-unclustered";
const tourismLabelLayerId = "public-map-tourism-label";
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
  cuisine_icon: string;
  is_selected: boolean;
};

type TourismFeatureProperties = {
  tourism_place_id: string;
  tourism_category: TourismPlace["category"];
  tourism_icon?: string;
  tourism_color: string;
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
        cuisine_icon: cuisineIconName(restaurant.primary_cuisine.icon_key),
        is_selected: restaurant.id === selectedRestaurantId,
      },
    })),
  };
}

const cuisineIconPrefix = "bitemap-cuisine-";
const tourismFallbackIconByDataset = {
  food: { iconKey: "tools-kitchen-3", color: "#F26B4F" },
  attraction: { iconKey: "map-pin", color: "#657B8C" },
  hotel: { iconKey: "bed", color: "#8B6BB1" },
  service_site: { iconKey: "info-circle", color: "#4E8F6B" },
} as const;

function cuisineIconName(iconKey: string): string {
  const normalized = iconKey.toLowerCase().replace(/[^a-z0-9-]/g, "-");
  return `${cuisineIconPrefix}${normalized || "default"}`;
}

function cuisineIconShape(iconKey: string): string {
  const normalized = iconKey.toLowerCase();
  if (normalized.includes("rice-bowl") || normalized.includes("bowl")) {
    return '<path d="M6 13h20l-2 9H8l-2-9Zm4-4h12M11 22v4M21 22v4" />';
  }
  if (normalized.includes("burger")) {
    return '<path d="M7 13h18M8 10c1.5-4 14.5-4 16 0M7 16h18M9 20h14" />';
  }
  if (normalized.includes("leaf") || normalized.includes("vegetable")) {
    return '<path d="M8 21C8 11 14 6 25 5c-1 11-6 17-17 16Zm1 0 10-10" />';
  }
  if (normalized.includes("fish") || normalized.includes("seafood")) {
    return '<path d="M5 16c5-7 12-7 19 0-7 7-14 7-19 0Zm19 0 4-4v8l-4-4ZM11 14h.01M11 18h.01" />';
  }
  if (normalized.includes("coffee") || normalized.includes("drink")) {
    return '<path d="M8 10h15v10a4 4 0 0 1-4 4h-7a4 4 0 0 1-4-4V10Zm15 3h2a3 3 0 0 1 0 6h-2M11 6c0-2 2-2 2-4M16 6c0-2 2-2 2-4" />';
  }
  if (normalized.includes("hot-pot") || normalized.includes("taiwan")) {
    return '<path d="M6 13h20l-2 9H8l-2-9Zm4-4h12M13 5v4M19 5v4M9 26h14" />';
  }
  if (normalized.includes("bed") || normalized.includes("lodging")) {
    return '<path d="M5 20v-9h22v9M5 16h22M8 11V8h6a3 3 0 0 1 3 3M5 24v-4M27 24v-4" />';
  }
  if (normalized.includes("home")) {
    return '<path d="m5 14 11-9 11 9v12H5V14Zm7 12v-7h8v7" />';
  }
  if (normalized.includes("info")) {
    return '<circle cx="16" cy="16" r="11" /><path d="M16 14v7M16 10h.01" />';
  }
  if (normalized.includes("tree") || normalized.includes("park")) {
    return '<path d="M16 5 9 15h4l-5 7h16l-5-7h4L16 5ZM16 22v5" />';
  }
  if (normalized.includes("confetti") || normalized.includes("play")) {
    return '<path d="m7 24 12-12 6 6L13 30 7 24Zm3-13 3-3m5 1 2-4m2 9 4-1" />';
  }
  if (normalized.includes("bank") || normalized.includes("culture")) {
    return '<path d="m4 12 12-7 12 7H4Zm3 3v6m5-6v6m8-6v6m5-6v6M4 25h24" />';
  }
  if (normalized.includes("mountain") || normalized.includes("nature")) {
    return '<path d="m4 25 8-12 4 6 3-4 7 10H4Zm8-12 3-5 4 7" />';
  }
  if (normalized.includes("store") || normalized.includes("shopping")) {
    return '<path d="M6 13h20l-2-7H8l-2 7Zm0 0v13h20V13M11 18h10v8H11" />';
  }
  if (normalized.includes("map-pin")) {
    return '<path d="M16 28s8-7.2 8-14a8 8 0 1 0-16 0c0 6.8 8 14 8 14Z" /><circle cx="16" cy="14" r="2.5" />';
  }
  return '<path d="M9 5v9M6 5v6a3 3 0 0 0 6 0V5M9 14v12M20 5v21M20 5c4 3 4 8 0 11" />';
}

function cuisineIconSvg(iconKey: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none"><g stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${cuisineIconShape(iconKey)}</g></svg>`;
}

async function cuisineIconImageData(iconKey: string): Promise<ImageData> {
  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(cuisineIconSvg(iconKey))}`;
  await image.decode();

  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("2D canvas context is unavailable");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return context.getImageData(0, 0, canvas.width, canvas.height);
}

async function ensureCuisineIcons(map: MapLibreMap, iconKeys: string[]): Promise<void> {
  const uniqueIconKeys = [...new Set(iconKeys)];
  await Promise.all(
    uniqueIconKeys.map(async (iconKey) => {
      const imageName = cuisineIconName(iconKey);
      if (map.hasImage(imageName)) return;
      try {
        const imageData = await cuisineIconImageData(iconKey);
        if (!map.hasImage(imageName)) map.addImage(imageName, imageData, { pixelRatio: 4 });
      } catch (error) {
        console.error(`Failed to create map icon "${iconKey}"`, error);
      }
    }),
  );
}

function tourismIconKey(place: TourismPlace): string {
  return place.icon_key ?? tourismFallbackIconByDataset[place.source_dataset].iconKey;
}

function tourismFeatureCollection(places: TourismPlace[]) {
  return {
    type: "FeatureCollection" as const,
    features: places.map((place) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: [place.longitude, place.latitude] as [number, number],
      },
      properties: {
        tourism_place_id: place.id,
        tourism_category: place.category,
        tourism_icon: cuisineIconName(tourismIconKey(place)),
        tourism_color: place.icon_key
          ? place.icon_color
          : tourismFallbackIconByDataset[place.source_dataset].color,
      } satisfies TourismFeatureProperties,
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
      "icon-image": ["get", "cuisine_icon"],
      "icon-size": ["case", ["get", "is_selected"], 0.9, 0.75],
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
}

function addTourismSourceAndLayers(map: MapLibreMap) {
  if (map.getSource(tourismSourceId)) return;

  map.addSource(tourismSourceId, {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
    cluster: true,
    clusterMaxZoom: 13,
    clusterRadius: 50,
  });
  map.addLayer({
    id: tourismClusterLayerId,
    type: "circle",
    source: tourismSourceId,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#657b8c",
      "circle-radius": ["step", ["get", "point_count"], 18, 10, 22, 50, 27],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: tourismClusterCountLayerId,
    type: "symbol",
    source: tourismSourceId,
    filter: ["has", "point_count"],
    layout: {
      "text-field": [
        "case",
        [">", ["get", "point_count"], 100],
        "100+",
        ["to-string", ["get", "point_count"]],
      ],
      "text-size": 12,
      "text-font": ["Open Sans Bold"],
    },
    paint: { "text-color": "#ffffff" },
  });
  map.addLayer({
    id: tourismLayerId,
    type: "circle",
    source: tourismSourceId,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": ["get", "tourism_color"],
      "circle-radius": 12,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: tourismLabelLayerId,
    type: "symbol",
    source: tourismSourceId,
    filter: ["all", ["!", ["has", "point_count"]], ["has", "tourism_icon"]],
    layout: {
      "icon-image": ["get", "tourism_icon"],
      "icon-size": 0.8,
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
}

function sourceFromMap(map: MapLibreMap) {
  return map.getSource(restaurantSourceId) as GeoJSONSource | undefined;
}

function tourismSourceFromMap(map: MapLibreMap) {
  return map.getSource(tourismSourceId) as GeoJSONSource | undefined;
}

function featureAtMapPoint(map: MapLibreMap, event: MapMouseEvent) {
  return map.queryRenderedFeatures(event.point, {
    layers: [
      clusterLayerId,
      clusterCountLayerId,
      restaurantLayerId,
      tourismClusterLayerId,
      tourismClusterCountLayerId,
      tourismLayerId,
    ],
  })[0] as MapGeoJSONFeature | undefined;
}

export function PublicMapPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error">("loading");
  const [restaurants, setRestaurants] = useState<MapRestaurant[]>([]);
  const [tourismPlaces, setTourismPlaces] = useState<TourismPlace[]>([]);
  const restaurantsRef = useRef<MapRestaurant[]>([]);
  const tourismPlacesRef = useRef<TourismPlace[]>([]);
  restaurantsRef.current = restaurants;
  tourismPlacesRef.current = tourismPlaces;
  const [selectedRestaurant, setSelectedRestaurant] = useState<MapRestaurant | null>(null);
  const [selectedTourismPlace, setSelectedTourismPlace] = useState<TourismPlace | null>(null);
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
        setTourismPlaces([]);
        setSelectedRestaurant(null);
        setSelectedTourismPlace(null);
        setMessage("群聚展示模式：中原附近 10 筆測試資料");
        return;
      }

      const [restaurantResult, tourismResult] = await Promise.allSettled([
        activeFiltersRef.current.showBiteMapRestaurants
          ? fetchPublicMapRestaurants(
              currentBounds(map),
              activeFiltersRef.current,
              controller.signal,
            )
          : Promise.resolve({ status: "ok" as const, restaurants: [] }),
        activeFiltersRef.current.showTourismData
          ? fetchPublicTourismPlaces(currentBounds(map), controller.signal)
          : Promise.resolve({ places: [] as TourismPlace[], has_more: false }),
      ]);
      if (
        activeFiltersRef.current.showBiteMapRestaurants &&
        restaurantResult.status === "rejected"
      ) {
        throw restaurantResult.reason;
      }
      const response =
        restaurantResult.status === "fulfilled"
          ? restaurantResult.value
          : { status: "ok" as const, restaurants: [] };
      const tourismResponse =
        tourismResult.status === "fulfilled"
          ? tourismResult.value
          : { places: [] as TourismPlace[], has_more: false };
      setTourismPlaces(tourismResponse.places);
      if (response.status === "zoom_required") {
        setRestaurants(response.restaurants);
        setSelectedRestaurant(null);
        setSelectedTourismPlace(null);
        setMessage("範圍較大，先顯示部分店家；放大地圖可查看更完整的群聚。");
        return;
      }
      setRestaurants(response.restaurants);
      setSelectedRestaurant(null);
      setSelectedTourismPlace(null);
      const center = map.getCenter();
      window.localStorage.setItem(
        viewportStorageKey,
        JSON.stringify({ longitude: center.lng, latitude: center.lat, zoom: map.getZoom() }),
      );
      if (
        !activeFiltersRef.current.showBiteMapRestaurants &&
        !activeFiltersRef.current.showTourismData
      ) {
        setMessage("請至少選擇一種資料來源，才能顯示店家。");
      } else if (!activeFiltersRef.current.showBiteMapRestaurants) {
        setMessage(`目前顯示 ${tourismResponse.places.length} 筆觀光署資料`);
      } else if (response.restaurants.length === 0) {
        setMessage(
          hasMapFilters(activeFiltersRef.current)
            ? "這個區域沒有符合條件的店家。"
            : "這個區域目前沒有已發布店家。",
        );
      } else {
        setMessage(
          activeFiltersRef.current.showTourismData
            ? `找到 ${response.restaurants.length} 間 BiteMap 店家，另有 ${tourismResponse.places.length} 筆觀光署資料`
            : `找到 ${response.restaurants.length} 間 BiteMap 店家`,
        );
      }
      if (tourismResult.status === "rejected") {
        setMessage(
          activeFiltersRef.current.showBiteMapRestaurants
            ? "BiteMap 店家已載入；觀光署資料暫時無法取得。"
            : "觀光署資料暫時無法取得，請稍後重試。",
        );
      }
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
        addTourismSourceAndLayers(map);
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
          setSelectedTourismPlace(null);
          setSearchResults(null);
          setIsFilterOpen(false);
          return;
        }

        const isTourismFeature = [
          tourismClusterLayerId,
          tourismClusterCountLayerId,
          tourismLayerId,
        ].includes(feature.layer?.id ?? "");
        if (feature.properties?.cluster_id !== undefined) {
          const source = isTourismFeature ? tourismSourceFromMap(map) : sourceFromMap(map);
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

        if (isTourismFeature) {
          const tourismPlaceId = String(feature.properties?.tourism_place_id ?? "");
          const tourismPlace = tourismPlacesRef.current.find((item) => item.id === tourismPlaceId);
          if (tourismPlace) {
            setSelectedRestaurant(null);
            setSelectedTourismPlace(tourismPlace);
          }
          return;
        }

        const restaurantId = String(feature.properties?.restaurant_id ?? "");
        const restaurant = restaurantsRef.current.find((item) => item.id === restaurantId);
        if (restaurant) {
          setSelectedTourismPlace(null);
          setSelectedRestaurant(restaurant);
        }
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
    if (!map || !source || mapStatus !== "ready") return;
    void ensureCuisineIcons(
      map,
      restaurants.map((restaurant) => restaurant.primary_cuisine.icon_key),
    ).then(() => {
      if (mapRef.current !== map) return;
      source.setData(restaurantFeatureCollection(restaurants, selectedRestaurant?.id ?? null));
    });
  }, [mapStatus, restaurants, selectedRestaurant]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map ? tourismSourceFromMap(map) : undefined;
    if (!map || !source || mapStatus !== "ready") return;
    void ensureCuisineIcons(
      map,
      tourismPlaces.map(tourismIconKey),
    ).then(() => {
      if (mapRef.current !== map) return;
      source.setData(tourismFeatureCollection(tourismPlaces));
    });
  }, [mapStatus, tourismPlaces]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapStatus !== "ready") return;
    const visibility = activeFilters.showBiteMapRestaurants ? "visible" : "none";
    [clusterLayerId, clusterCountLayerId, restaurantLayerId, restaurantLabelLayerId].forEach(
      (layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", visibility);
      },
    );
  }, [activeFilters.showBiteMapRestaurants, mapStatus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapStatus !== "ready") return;
    const visibility = activeFilters.showTourismData ? "visible" : "none";
    [
      tourismClusterLayerId,
      tourismClusterCountLayerId,
      tourismLayerId,
      tourismLabelLayerId,
    ].forEach((layerId) => {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", visibility);
    });
  }, [activeFilters.showTourismData, mapStatus]);

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
    if (!nextFilters.showBiteMapRestaurants) setSelectedRestaurant(null);
    if (!nextFilters.showTourismData) setSelectedTourismPlace(null);
    setActiveFilters(nextFilters);
    activeFiltersRef.current = nextFilters;
    setPendingFilters(cloneMapFilters(nextFilters));
    setIsFilterOpen(false);
    setMessage("篩選條件已更新，正在重新載入店家。");
    if (mapRef.current && mapStatus === "ready") void searchMap(mapRef.current);
  }

  function removeFilter(
    key:
      | "city"
      | "district"
      | "priceRange"
      | "cuisine"
      | "biteMapSource"
      | "tourismSource",
    value?: string,
  ) {
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
    } else if (key === "biteMapSource") {
      nextFilters.showBiteMapRestaurants = true;
    } else if (key === "tourismSource") {
      nextFilters.showTourismData = true;
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
      {selectedTourismPlace ? (
        <TourismPreviewCard
          place={selectedTourismPlace}
          onClose={() => setSelectedTourismPlace(null)}
        />
      ) : null}
    </main>
  );
}
