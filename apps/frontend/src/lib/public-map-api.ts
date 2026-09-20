import type { PriceRange } from "@/lib/admin-api";

export type MapBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
  zoom: number;
};

export type MapCuisine = {
  id: string;
  display_name: string;
  color: string;
  icon_key: string;
};

export type MapRestaurant = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  primary_cuisine: MapCuisine;
  price_range: PriceRange;
  menu_url: string | null;
};

export type MapRestaurantsResponse = {
  status: "ok" | "zoom_required";
  restaurants: MapRestaurant[];
};

export type MapSearchLocation = {
  label: string;
  region: string | null;
  latitude: number;
  longitude: number;
  source: string;
};

export type MapSearchResponse = {
  status: "ok" | "partial";
  locations: MapSearchLocation[];
  restaurants: MapRestaurant[];
};

export type MapFilters = {
  city: string;
  district: string;
  cuisineIds: string[];
  priceRanges: PriceRange[];
};

export const defaultMapFilters: MapFilters = {
  city: "",
  district: "",
  cuisineIds: [],
  priceRanges: [],
};

export class PublicMapApiError extends Error {
  constructor(public readonly status: number) {
    super("Public map request failed");
  }
}

export function publicMapSearchParams(
  bounds: MapBounds,
  filters: MapFilters = defaultMapFilters,
): URLSearchParams {
  const params = new URLSearchParams({
    west: String(bounds.west),
    south: String(bounds.south),
    east: String(bounds.east),
    north: String(bounds.north),
    zoom: String(bounds.zoom),
  });
  if (filters.city) params.set("city", filters.city);
  if (filters.district) params.set("district", filters.district);
  filters.cuisineIds.forEach((id) => params.append("cuisine_ids", id));
  filters.priceRanges.forEach((priceRange) => params.append("price_ranges", priceRange));
  return params;
}

export async function fetchPublicMapRestaurants(
  bounds: MapBounds,
  filters: MapFilters = defaultMapFilters,
  signal?: AbortSignal,
): Promise<MapRestaurantsResponse> {
  const response = await fetch(
    `/api/v1/map/restaurants?${publicMapSearchParams(bounds, filters)}`,
    {
      signal,
    },
  );
  if (!response.ok) throw new PublicMapApiError(response.status);
  return (await response.json()) as MapRestaurantsResponse;
}

export async function fetchPublicMapSearch(
  query: string,
  signal?: AbortSignal,
): Promise<MapSearchResponse> {
  const response = await fetch(`/api/v1/map/search?q=${encodeURIComponent(query)}&limit=5`, {
    signal,
  });
  if (!response.ok) throw new PublicMapApiError(response.status);
  return (await response.json()) as MapSearchResponse;
}

export async function fetchPublicMapCuisines(signal?: AbortSignal): Promise<MapCuisine[]> {
  const response = await fetch("/api/v1/map/cuisines", { signal });
  if (!response.ok) throw new PublicMapApiError(response.status);
  return (await response.json()) as MapCuisine[];
}

export const priceRangeLabels: Record<PriceRange, string> = {
  under_200: "$200 以下",
  "200_to_400": "$200–400",
  "400_to_800": "$400–800",
  over_800: "$800 以上",
};
