/** Administrator API client / 管理員 API Client。 */

export type Cuisine = {
  id: string;
  slug: string;
  display_name: string;
  color: string;
  icon_key: string;
  is_active: boolean;
};

export type PriceRange = "under_200" | "200_to_400" | "400_to_800" | "over_800";

export type Restaurant = {
  id: string;
  name: string;
  address: string;
  menu_url: string | null;
  google_place_id: string | null;
  google_lookup_enabled: boolean;
  primary_cuisine_id: string | null;
  primary_cuisine: Cuisine | null;
  price_range: PriceRange | null;
  status: "draft" | "published" | "archived";
  source_type: "manual";
  latitude: number | null;
  longitude: number | null;
  created_at: string;
  updated_at: string;
};

export type RestaurantMenu = {
  id: string;
  restaurant_id: string;
  title: string;
  url: string;
  last_updated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RestaurantPhoto = {
  id: string;
  restaurant_id: string;
  url: string;
  alt_text: string | null;
  sort_order: number;
  created_at: string;
};

export type AvatarAsset = {
  id: string;
  display_name: string;
  url: string;
  mime_type: string;
  file_size: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MapQueryMetric = {
  occurred_at: string;
  duration_ms: number;
  result_count: number;
  cache_hit: boolean;
  response_status: "ok" | "zoom_required" | "error";
  query_summary: string;
};

export type MapPerformanceMetrics = {
  window_minutes: number;
  query_count: number;
  average_duration_ms: number;
  p95_duration_ms: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
  zoom_required_count: number;
  zoom_required_rate: number;
  error_count: number;
  error_rate: number;
  published_restaurant_count: number;
  cache_entries: number;
  status: "normal" | "attention" | "critical";
  alerts: string[];
  last_updated_at: string;
  recent_queries: MapQueryMetric[];
};

export type TourismImportRun = {
  id: string;
  source_dataset: "food" | "attraction" | "hotel" | "service_site";
  source_url: string;
  status: "running" | "succeeded" | "failed";
  started_at: string;
  completed_at: string | null;
  downloaded_count: number;
  inserted_count: number;
  updated_count: number;
  unchanged_count: number;
  invalid_count: number;
  deactivated_count: number;
  error_message: string | null;
};

export type TourismImportStart = {
  status: "started" | "already_running";
  datasets: TourismImportRun["source_dataset"][];
};

export type TourismAdminPlace = {
  id: string;
  source_dataset: TourismImportRun["source_dataset"];
  source_record_id: string;
  category: "restaurant" | "attraction" | "hotel" | "service_site";
  name: string;
  official_name: string;
  address: string | null;
  official_address: string | null;
  icon_key: string | null;
  icon_classification_slug: string | null;
  official_icon_key: string;
  icon_color: string;
  latitude: number;
  longitude: number;
  is_map_enabled: boolean;
  linked_restaurant_id: string | null;
};

export type TourismPlaceDeleteResponse = { deleted: boolean };
export type TourismPlacesDeleteResponse = { deleted_count: number; deleted_ids: string[] };

export type TourismAdminPlacesResponse = {
  places: TourismAdminPlace[];
  total: number;
  has_more: boolean;
};

export type TourismDuplicatePair = {
  left: TourismAdminPlace;
  right: TourismAdminPlace;
  name_similarity: number;
  match_reasons: string[];
};

export type TourismDuplicatePairsResponse = {
  pairs: TourismDuplicatePair[];
  total: number;
  has_more: boolean;
};

export class AdminApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "Request failed");
  }
}

export async function adminApi<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const headers = new Headers(init?.headers);
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/v1/admin${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new AdminApiError(response.status, payload.detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const priceRangeLabels: Record<PriceRange, string> = {
  under_200: "$200 以下",
  "200_to_400": "$200–400",
  "400_to_800": "$400–800",
  over_800: "$800 以上",
};
