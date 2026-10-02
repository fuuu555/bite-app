/** Restaurant review and favorite API client / 餐廳留言與收藏 API Client。 */

export type RevisitStatus = "will_return" | "neutral" | "will_not_return";
export type ReviewSort = "featured" | "latest" | "popular";
export type ReviewStatusFilter = "all" | RevisitStatus;

export type ReviewReason = {
  id: string;
  slug: string;
  display_name: string;
  polarity: "positive" | "negative";
};

export type RestaurantReview = {
  id: string;
  thread_id: string;
  entry_number: number;
  is_revisit: boolean;
  author_id: string;
  author_display_name: string;
  author_avatar_url: string | null;
  content: string;
  revisit_status: RevisitStatus;
  reasons: ReviewReason[];
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  is_deleted: boolean;
  revisit_count: number;
  like_count: number;
  liked_by_me: boolean;
  is_owner: boolean;
};

export type ReviewList = {
  reviews: RestaurantReview[];
  total: number;
  sort: ReviewSort;
  status: ReviewStatusFilter;
  available_reasons: ReviewReason[];
  has_current_user_review: boolean;
};

export type FavoriteRestaurant = {
  id: string;
  name: string;
  address: string;
  primary_cuisine: {
    id: string;
    display_name: string;
    color: string;
    icon_key: string;
  };
  price_range: "under_200" | "200_to_400" | "400_to_800" | "over_800";
  menu_url: string | null;
  photo_url: string | null;
  created_at: string;
};

export type ProfileReview = {
  id: string;
  restaurant_id: string;
  restaurant_name: string;
  restaurant_photo_url: string | null;
  entry_number: number;
  is_revisit: boolean;
  content: string;
  revisit_status: RevisitStatus;
  reasons: ReviewReason[];
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  revisit_count: number;
};

export class ReviewsApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "Request failed");
  }
}

async function reviewsApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new ReviewsApiError(response.status, payload.detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fetchRestaurantReviews(
  restaurantId: string,
  sort: ReviewSort,
  status: ReviewStatusFilter,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ sort, status });
  return reviewsApi<ReviewList>(
    `/explore/restaurants/${encodeURIComponent(restaurantId)}/reviews?${params}`,
    { signal },
  );
}

export function createRestaurantReview(
  restaurantId: string,
  payload: { content: string; revisit_status: RevisitStatus; reason_ids: string[] },
) {
  return reviewsApi<RestaurantReview>(
    `/explore/restaurants/${encodeURIComponent(restaurantId)}/reviews`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function updateRestaurantReview(
  reviewId: string,
  payload: { content: string; revisit_status: RevisitStatus; reason_ids: string[] },
) {
  return reviewsApi<RestaurantReview>(`/reviews/${encodeURIComponent(reviewId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRestaurantReview(reviewId: string) {
  return reviewsApi<void>(`/reviews/${encodeURIComponent(reviewId)}`, { method: "DELETE" });
}

export function toggleReviewLike(reviewId: string, liked: boolean) {
  return reviewsApi<{ liked: boolean; like_count: number }>(
    `/reviews/${encodeURIComponent(reviewId)}/like`,
    { method: liked ? "POST" : "DELETE" },
  );
}

export function fetchReviewTimeline(restaurantId: string, reviewId: string) {
  return reviewsApi<{ reviews: RestaurantReview[] }>(
    `/explore/restaurants/${encodeURIComponent(restaurantId)}/reviews/${encodeURIComponent(reviewId)}/timeline`,
  );
}

export function fetchFavoriteState(restaurantId: string) {
  return reviewsApi<{ favorited: boolean }>(
    `/restaurants/${encodeURIComponent(restaurantId)}/favorite`,
  );
}

export function setFavorite(restaurantId: string, favorited: boolean) {
  return reviewsApi<void>(`/restaurants/${encodeURIComponent(restaurantId)}/favorite`, {
    method: favorited ? "POST" : "DELETE",
  });
}

export function fetchMyFavorites() {
  return reviewsApi<{ restaurants: FavoriteRestaurant[]; total: number }>("/me/favorites");
}

export function fetchMyReviews() {
  return reviewsApi<{ reviews: ProfileReview[]; total: number }>("/me/reviews");
}
