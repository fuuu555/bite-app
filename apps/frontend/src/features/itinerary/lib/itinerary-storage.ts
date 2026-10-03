import type { MapRestaurant, TourismPlace } from "@/features/map/api/public-map-api";
import type { ItineraryPlace } from "@/features/itinerary/api/itinerary-api";

export const itineraryStorageKey = "bitemap-itinerary-v1";

export type ItineraryCategory = "restaurant" | "attraction" | "hotel" | "service_site";
export type ItinerarySource = "bitemap" | "tourism";

export type SavedItineraryPlace = {
  id: string;
  source: ItinerarySource;
  source_dataset: string;
  source_record_id: string;
  category: ItineraryCategory;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  official_url: string | null;
  opening_hours: string | null;
  source_updated_at: string | null;
  icon_color: string;
};

export type SavedItinerary = {
  version: 1;
  updatedAt: string;
  places: SavedItineraryPlace[];
};

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function emptyItinerary(): SavedItinerary {
  return { version: 1, updatedAt: new Date(0).toISOString(), places: [] };
}

function browserStorage(): StorageLike | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isValidPlace(value: unknown): value is SavedItineraryPlace {
  if (!value || typeof value !== "object") return false;
  const place = value as Partial<SavedItineraryPlace>;
  return (
    typeof place.id === "string" &&
    (place.source === "bitemap" || place.source === "tourism") &&
    typeof place.source_dataset === "string" &&
    typeof place.source_record_id === "string" &&
    ["restaurant", "attraction", "hotel", "service_site"].includes(place.category ?? "") &&
    typeof place.name === "string" &&
    (place.latitude === null || typeof place.latitude === "number") &&
    (place.longitude === null || typeof place.longitude === "number")
  );
}

function placeKey(place: Pick<SavedItineraryPlace, "source" | "source_record_id">) {
  return `${place.source}:${place.source_record_id}`;
}

export function readSavedItinerary(storage: StorageLike | null = browserStorage()): SavedItinerary {
  if (!storage) return emptyItinerary();
  try {
    const raw = storage.getItem(itineraryStorageKey);
    if (!raw) return emptyItinerary();
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return emptyItinerary();
    const candidate = parsed as Partial<SavedItinerary>;
    if (candidate.version !== 1 || !Array.isArray(candidate.places)) return emptyItinerary();
    const places = candidate.places.filter(isValidPlace);
    return {
      version: 1,
      updatedAt:
        typeof candidate.updatedAt === "string" ? candidate.updatedAt : new Date().toISOString(),
      places: places.filter(
        (place, index, all) =>
          all.findIndex((item) => placeKey(item) === placeKey(place)) === index,
      ),
    };
  } catch {
    return emptyItinerary();
  }
}

export function writeSavedItinerary(
  itinerary: SavedItinerary,
  storage: StorageLike | null = browserStorage(),
): boolean {
  if (!storage) return false;
  try {
    storage.setItem(
      itineraryStorageKey,
      JSON.stringify({ ...itinerary, version: 1, updatedAt: new Date().toISOString() }),
    );
    return true;
  } catch {
    return false;
  }
}

export function addItineraryPlace(
  itinerary: SavedItinerary,
  place: SavedItineraryPlace,
): SavedItinerary {
  if (itinerary.places.some((item) => placeKey(item) === placeKey(place))) return itinerary;
  return {
    ...itinerary,
    updatedAt: new Date().toISOString(),
    places: [...itinerary.places, place],
  };
}

export function removeItineraryPlace(
  itinerary: SavedItinerary,
  place: Pick<SavedItineraryPlace, "source" | "source_record_id">,
) {
  return {
    ...itinerary,
    updatedAt: new Date().toISOString(),
    places: itinerary.places.filter((item) => placeKey(item) !== placeKey(place)),
  };
}

export function moveItineraryPlace(
  itinerary: SavedItinerary,
  fromIndex: number,
  toIndex: number,
): SavedItinerary {
  if (
    fromIndex < 0 ||
    fromIndex >= itinerary.places.length ||
    toIndex < 0 ||
    toIndex >= itinerary.places.length ||
    fromIndex === toIndex
  ) {
    return itinerary;
  }
  const places = [...itinerary.places];
  const [moved] = places.splice(fromIndex, 1);
  places.splice(toIndex, 0, moved);
  return { ...itinerary, updatedAt: new Date().toISOString(), places };
}

export function clearItinerary(): SavedItinerary {
  return emptyItinerary();
}

export function isPlaceInItinerary(
  itinerary: SavedItinerary,
  place: Pick<SavedItineraryPlace, "source" | "source_record_id">,
) {
  return itinerary.places.some((item) => placeKey(item) === placeKey(place));
}

export function getItineraryCategoryLabel(category: ItineraryCategory) {
  return {
    restaurant: "吃飯",
    attraction: "景點",
    hotel: "住宿",
    service_site: "服務站",
  }[category];
}

export function toRestaurantItineraryPlace(restaurant: MapRestaurant): SavedItineraryPlace {
  return {
    id: restaurant.id,
    source: "bitemap",
    source_dataset: "bitemap",
    source_record_id: restaurant.id,
    category: "restaurant",
    name: restaurant.name,
    address: null,
    latitude: restaurant.latitude,
    longitude: restaurant.longitude,
    official_url: restaurant.menu_url,
    opening_hours: null,
    source_updated_at: null,
    icon_color: restaurant.primary_cuisine.color,
  };
}

export function toTourismItineraryPlace(place: TourismPlace): SavedItineraryPlace {
  return {
    id: place.id,
    source: "tourism",
    source_dataset: place.source_dataset,
    source_record_id: place.source_record_id,
    category: place.category,
    name: place.name,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    official_url: place.official_url,
    opening_hours: place.opening_hours,
    source_updated_at: place.source_updated_at,
    icon_color: place.icon_color,
  };
}

export function toPlannedItineraryPlace(place: ItineraryPlace): SavedItineraryPlace {
  return {
    id: place.id,
    source: place.source,
    source_dataset: place.source_dataset,
    source_record_id: place.source_record_id ?? place.id,
    category: place.category,
    name: place.name,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    official_url: place.official_url,
    opening_hours: place.opening_hours,
    source_updated_at: place.source_updated_at,
    icon_color: place.icon_color,
  };
}

export function buildGoogleMapsDirectionsUrl(
  places: SavedItineraryPlace[],
  origin?: { latitude: number; longitude: number } | null,
) {
  const validPlaces = places.filter(
    (place) =>
      typeof place.latitude === "number" &&
      Number.isFinite(place.latitude) &&
      typeof place.longitude === "number" &&
      Number.isFinite(place.longitude),
  );
  if (!validPlaces.length) return null;

  const point = (place: SavedItineraryPlace) => `${place.latitude},${place.longitude}`;
  if (validPlaces.length === 1) {
    return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(point(validPlaces[0]))}`;
  }

  const destination = point(validPlaces[validPlaces.length - 1]);
  const waypoints = validPlaces.slice(0, -1).map(point);
  const start = origin ? `${origin.latitude},${origin.longitude}` : waypoints.shift();
  const params = new URLSearchParams({
    api: "1",
    origin: start ?? destination,
    destination,
  });
  if (waypoints.length) params.set("waypoints", waypoints.join("|"));
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
