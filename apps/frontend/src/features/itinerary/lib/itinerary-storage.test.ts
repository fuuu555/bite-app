import { describe, expect, it } from "vitest";

import {
  addItineraryPlace,
  buildItineraryRouteLine,
  buildGoogleMapsDirectionsUrl,
  emptyItinerary,
  moveItineraryPlace,
  readSavedItinerary,
  removeItineraryPlace,
  writeSavedItinerary,
  type SavedItineraryPlace,
} from "./itinerary-storage";

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };
}

const restaurant: SavedItineraryPlace = {
  id: "restaurant-1",
  source: "bitemap",
  source_dataset: "bitemap",
  source_record_id: "restaurant-1",
  category: "restaurant",
  name: "測試餐廳",
  address: "桃園市中壢區",
  latitude: 24.95,
  longitude: 121.22,
  official_url: null,
  opening_hours: null,
  source_updated_at: null,
  icon_color: "#d96c4f",
};

const attraction = {
  ...restaurant,
  id: "attraction-1",
  source: "tourism" as const,
  source_record_id: "attraction-1",
  category: "attraction" as const,
  name: "測試景點",
  latitude: 24.96,
  longitude: 121.23,
};

describe("itinerary storage", () => {
  it("round trips a versioned itinerary and removes duplicates", () => {
    const storage = createStorage();
    const initial = emptyItinerary();
    const withRestaurant = addItineraryPlace(initial, restaurant);
    const withDuplicate = addItineraryPlace(withRestaurant, restaurant);

    expect(withDuplicate.places).toHaveLength(1);
    expect(writeSavedItinerary(withDuplicate, storage)).toBe(true);
    expect(readSavedItinerary(storage)).toEqual(expect.objectContaining({ places: [restaurant] }));
  });

  it("falls back to an empty itinerary when stored data is invalid", () => {
    const storage = createStorage();
    storage.setItem("bitemap-itinerary-v1", "not-json");

    expect(readSavedItinerary(storage).places).toEqual([]);
  });

  it("moves and removes places without mutating the original itinerary", () => {
    const itinerary = addItineraryPlace(
      addItineraryPlace(emptyItinerary(), restaurant),
      attraction,
    );
    const moved = moveItineraryPlace(itinerary, 1, 0);
    const removed = removeItineraryPlace(moved, attraction);

    expect(itinerary.places.map((place) => place.name)).toEqual(["測試餐廳", "測試景點"]);
    expect(moved.places.map((place) => place.name)).toEqual(["測試景點", "測試餐廳"]);
    expect(removed.places.map((place) => place.name)).toEqual(["測試餐廳"]);
  });

  it("builds a Google Maps multi-stop route in itinerary order", () => {
    const url = buildGoogleMapsDirectionsUrl([restaurant, attraction], {
      latitude: 24.94,
      longitude: 121.21,
    });

    expect(url).toContain("https://www.google.com/maps/dir/?");
    expect(url).toContain("origin=24.94%2C121.21");
    expect(url).toContain("destination=24.96%2C121.23");
    expect(url).toContain("waypoints=24.95%2C121.22");
  });

  it("builds an internal route line and skips places without coordinates", () => {
    expect(
      buildItineraryRouteLine([restaurant, { latitude: null, longitude: null }, attraction]),
    ).toEqual([
      [121.22, 24.95],
      [121.23, 24.96],
    ]);
  });
});
