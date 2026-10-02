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
