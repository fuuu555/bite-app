import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchPublicMapRestaurants,
  publicMapSearchParams,
  type MapFilters,
} from "./public-map-api";

const bounds = {
  west: 121.18,
  south: 24.9,
  east: 121.28,
  north: 25,
  zoom: 13,
};

describe("public map API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("serializes the current viewport", () => {
    expect(publicMapSearchParams(bounds).toString()).toBe(
      "west=121.18&south=24.9&east=121.28&north=25&zoom=13",
    );
  });

  it("returns the bounded restaurant payload", async () => {
    const payload = { status: "ok" as const, restaurants: [] };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPublicMapRestaurants(bounds)).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/map/restaurants?west=121.18&south=24.9&east=121.28&north=25&zoom=13",
      { signal: undefined },
    );
  });

  it("serializes active map filters without changing the viewport contract", () => {
    const filters: MapFilters = {
      city: "桃園市",
      district: "中壢區",
      cuisineIds: ["cuisine-id"],
      priceRanges: ["200_to_400"],
    };

    expect(publicMapSearchParams(bounds, filters).toString()).toBe(
      "west=121.18&south=24.9&east=121.28&north=25&zoom=13&city=%E6%A1%83%E5%9C%92%E5%B8%82&district=%E4%B8%AD%E5%A3%A2%E5%8D%80&cuisine_ids=cuisine-id&price_ranges=200_to_400",
    );
  });
});
