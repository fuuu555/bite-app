import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ExploreApiError,
  FALLBACK_EXPLORE_LOCATION,
  explorePageSearchParams,
  exploreSearchParams,
  exploreUrlState,
  fetchExploreRestaurant,
  formatExploreDistance,
  type ExploreFilters,
} from "./explore-api";

describe("explore API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("serializes name and active conditions with the stable skeleton sort", () => {
    const filters: ExploreFilters = {
      cuisineId: "cuisine-id",
      priceRange: "200_to_400",
      distanceKm: "",
    };

    expect(exploreSearchParams("  拉麵  ", filters).toString()).toBe(
      "sort=stable&limit=24&q=%E6%8B%89%E9%BA%B5&cuisine_ids=cuisine-id&price_ranges=200_to_400",
    );
  });

  it("adds the selected distance and current location to the API request", () => {
    const params = exploreSearchParams(
      "",
      { cuisineId: "", priceRange: "", distanceKm: 5 },
      { latitude: 24.9537, longitude: 121.2258 },
    );

    expect(params.get("distance_km")).toBe("5");
    expect(params.get("latitude")).toBe("24.9537");
    expect(params.get("longitude")).toBe("121.2258");
  });

  it("serializes page conditions without empty URL parameters", () => {
    expect(
      explorePageSearchParams("  拉麵  ", {
        cuisineId: "cuisine-id",
        priceRange: "",
        distanceKm: "",
      }).toString(),
    ).toBe("q=%E6%8B%89%E9%BA%B5&cuisine=cuisine-id");
  });

  it("restores valid page conditions and ignores an unknown price", () => {
    expect(
      exploreUrlState(
        new URLSearchParams("q=%E6%8B%89%E9%BA%B5&cuisine=cuisine-id&price=200_to_400"),
      ),
    ).toEqual({
      query: "拉麵",
      filters: { cuisineId: "cuisine-id", priceRange: "200_to_400", distanceKm: "" },
    });
    expect(exploreUrlState(new URLSearchParams("price=not-a-price")).filters.priceRange).toBe("");
    expect(exploreUrlState(new URLSearchParams("distance=5")).filters.distanceKm).toBe(5);
  });

  it("exposes a not-found status for the restaurant detail skeleton", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));

    await expect(fetchExploreRestaurant("missing-id")).rejects.toEqual(
      expect.objectContaining<Partial<ExploreApiError>>({ status: 404 }),
    );
  });

  it("does not render a distance label before a location is available", () => {
    expect(formatExploreDistance(null)).toBeNull();
    expect(FALLBACK_EXPLORE_LOCATION).toEqual({ latitude: 24.9571129, longitude: 121.2425529 });
  });
});
