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

export class PublicMapApiError extends Error {
  constructor(public readonly status: number) {
    super("Public map request failed");
  }
}

export function publicMapSearchParams(bounds: MapBounds): URLSearchParams {
  return new URLSearchParams({
    west: String(bounds.west),
    south: String(bounds.south),
    east: String(bounds.east),
    north: String(bounds.north),
    zoom: String(bounds.zoom),
  });
}

export async function fetchPublicMapRestaurants(
  bounds: MapBounds,
  signal?: AbortSignal,
): Promise<MapRestaurantsResponse> {
  const response = await fetch(`/api/v1/map/restaurants?${publicMapSearchParams(bounds)}`, {
    signal,
  });
  if (!response.ok) throw new PublicMapApiError(response.status);
  return (await response.json()) as MapRestaurantsResponse;
}

export const priceRangeLabels: Record<PriceRange, string> = {
  under_200: "$200 以下",
  "200_to_400": "$200–400",
  "400_to_800": "$400–800",
  over_800: "$800 以上",
};
