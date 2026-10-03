export type ItineraryQuickAction = "eat" | "stay" | "attraction" | "plan";
export type ItineraryDuration = "half_day" | "full_day";
export type ItineraryTransport = "walking" | "public_transport" | "driving";
export type ItineraryPlaceCategory = "restaurant" | "attraction" | "hotel" | "service_site";

export type ItineraryPlanRequest = {
  latitude?: number;
  longitude?: number;
  city?: string;
  quick_action: ItineraryQuickAction;
  duration: ItineraryDuration;
  radius_km: 2 | 5 | 10;
  transport: ItineraryTransport;
  interests: string[];
  meal_preference?: string;
  include_lodging: boolean;
  prompt?: string;
};

export type ItineraryPlace = {
  id: string;
  source: "bitemap" | "tourism";
  source_dataset: "bitemap" | "food" | "attraction" | "hotel" | "service_site";
  source_record_id: string | null;
  category: ItineraryPlaceCategory;
  name: string;
  address: string | null;
  latitude: number;
  longitude: number;
  distance_meters: number;
  description: string | null;
  phone: string | null;
  official_url: string | null;
  opening_hours: string | null;
  source_updated_at: string | null;
  tags: string[];
  cuisine_name: string | null;
  price_range: "under_200" | "200_to_400" | "400_to_800" | "over_800" | null;
  icon_color: string;
};

export type ItineraryStop = {
  order: number;
  role: "attraction" | "meal" | "lodging" | "service_site";
  reason: string;
  suggested_duration_minutes: number;
  place: ItineraryPlace;
};

export type ItineraryPlan = {
  source: "ai" | "rules";
  title: string;
  summary: string;
  center_latitude: number;
  center_longitude: number;
  city: string | null;
  radius_km: number;
  intent: {
    city: string | null;
    duration: ItineraryDuration;
    transport: ItineraryTransport;
    interests: string[];
    meal_preference: string | null;
    include_lodging: boolean;
  };
  stops: ItineraryStop[];
  alternatives: ItineraryPlace[];
};

export class ItineraryApiError extends Error {
  constructor(
    public readonly status: number,
    message = "Itinerary request failed",
  ) {
    super(message);
  }
}

export async function fetchItineraryPlan(
  payload: ItineraryPlanRequest,
  signal?: AbortSignal,
): Promise<ItineraryPlan> {
  const response = await fetch("/api/v1/itinerary/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    let message = "行程推薦暫時無法使用。";
    try {
      const body = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the user-facing fallback when the server does not return JSON.
    }
    throw new ItineraryApiError(response.status, message);
  }
  return (await response.json()) as ItineraryPlan;
}
