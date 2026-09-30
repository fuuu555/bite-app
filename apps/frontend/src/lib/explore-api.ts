import type { PriceRange } from "@/lib/admin-api";
import type { MapCuisine } from "@/lib/public-map-api";

export type ExploreAppSignals = {
  revisit_rate: number | null;
  rating_count: number | null;
  will_return_count: number | null;
  neutral_count: number | null;
  will_not_return_count: number | null;
  trust_level: "high" | "medium" | "low" | null;
};

export type ExploreGoogleSignals = {
  rating: number | null;
  review_count: number | null;
};

export type ExploreDistanceKm = 2 | 5 | 10;

export type ExploreLocation = {
  latitude: number;
  longitude: number;
};

export function distanceBetweenLocations(first: ExploreLocation, second: ExploreLocation): number {
  const earthRadiusMeters = 6_371_000;
  const latitudeDelta = ((second.latitude - first.latitude) * Math.PI) / 180;
  const longitudeDelta = ((second.longitude - first.longitude) * Math.PI) / 180;
  const firstLatitude = (first.latitude * Math.PI) / 180;
  const secondLatitude = (second.latitude * Math.PI) / 180;
  const haversine =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(firstLatitude) * Math.cos(secondLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * earthRadiusMeters * Math.asin(Math.sqrt(haversine));
}

export function formatExploreDistance(distanceMeters: number | null): string {
  if (distanceMeters === null) return "尚未取得定位";
  if (distanceMeters < 1000) return `${Math.round(distanceMeters)} m`;
  return `${(distanceMeters / 1000).toFixed(1)} km`;
}

export type ExploreRestaurant = {
  id: string;
  name: string;
  address: string;
  primary_cuisine: MapCuisine;
  price_range: PriceRange;
  menu_url: string | null;
  photo_url: string | null;
  distance_meters: number | null;
  app: ExploreAppSignals;
  google: ExploreGoogleSignals;
};

export type ExploreRestaurantsResponse = {
  status: "ok";
  query: string | null;
  sort: "stable";
  top_restaurants: ExploreRestaurant[];
  restaurants: ExploreRestaurant[];
};

export type ExploreRestaurantDetail = ExploreRestaurant & {
  latitude: number | null;
  longitude: number | null;
  menu: {
    url: string | null;
    last_updated_at: string | null;
  };
  menus: ExploreMenuDocument[];
  photos: ExplorePhoto[];
};

export type ExploreMenuDocument = {
  id: string;
  title: string;
  url: string;
  last_updated_at: string | null;
};

export type ExplorePhoto = {
  id: string;
  url: string;
  alt_text: string | null;
};

export type ExploreFilters = {
  cuisineId: string;
  priceRange: PriceRange | "";
  distanceKm: ExploreDistanceKm | "";
};

export type ExploreUrlState = {
  query: string;
  filters: ExploreFilters;
};

export class ExploreApiError extends Error {
  constructor(public readonly status: number) {
    super("Explore request failed");
  }
}

type SearchParamReader = {
  get(name: string): string | null;
};

const validPriceRanges = new Set(["under_200", "200_to_400", "400_to_800", "over_800"]);
const validDistanceKm = new Set([2, 5, 10]);

export function explorePageSearchParams(query: string, filters: ExploreFilters): URLSearchParams {
  const params = new URLSearchParams();
  const normalizedQuery = query.trim();
  if (normalizedQuery) params.set("q", normalizedQuery);
  if (filters.cuisineId) params.set("cuisine", filters.cuisineId);
  if (filters.priceRange) params.set("price", filters.priceRange);
  if (filters.distanceKm) params.set("distance", String(filters.distanceKm));
  return params;
}

export function exploreUrlState(searchParams: SearchParamReader): ExploreUrlState {
  const priceRange = searchParams.get("price") ?? "";
  return {
    query: searchParams.get("q") ?? "",
    filters: {
      cuisineId: searchParams.get("cuisine") ?? "",
      priceRange: validPriceRanges.has(priceRange) ? (priceRange as PriceRange) : "",
      distanceKm: validDistanceKm.has(Number(searchParams.get("distance")))
        ? (Number(searchParams.get("distance")) as ExploreDistanceKm)
        : "",
    },
  };
}

export function exploreSearchParams(
  query: string,
  filters: ExploreFilters,
  location?: ExploreLocation,
): URLSearchParams {
  const params = new URLSearchParams({ sort: "stable", limit: "24" });
  const normalizedQuery = query.trim();
  if (normalizedQuery) params.set("q", normalizedQuery);
  if (filters.cuisineId) params.append("cuisine_ids", filters.cuisineId);
  if (filters.priceRange) params.append("price_ranges", filters.priceRange);
  if (filters.distanceKm && location) {
    params.set("distance_km", String(filters.distanceKm));
    params.set("latitude", String(location.latitude));
    params.set("longitude", String(location.longitude));
  }
  return params;
}

export async function fetchExploreRestaurants(
  query: string,
  filters: ExploreFilters,
  location?: ExploreLocation,
  signal?: AbortSignal,
): Promise<ExploreRestaurantsResponse> {
  const response = await fetch(
    `/api/v1/explore/restaurants?${exploreSearchParams(query, filters, location)}`,
    {
      signal,
    },
  );
  if (!response.ok) throw new ExploreApiError(response.status);
  return (await response.json()) as ExploreRestaurantsResponse;
}

export async function fetchExploreRestaurant(
  restaurantId: string,
  signal?: AbortSignal,
): Promise<ExploreRestaurantDetail> {
  const response = await fetch(`/api/v1/explore/restaurants/${encodeURIComponent(restaurantId)}`, {
    signal,
  });
  if (!response.ok) throw new ExploreApiError(response.status);
  return (await response.json()) as ExploreRestaurantDetail;
}
