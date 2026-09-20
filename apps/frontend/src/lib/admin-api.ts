/** Stage 1 administrator API client / Stage 1 管理 API Client。 */

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

export class AdminApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "Request failed");
  }
}

export async function adminApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/admin${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
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
