import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchPublicMapRestaurants, publicMapSearchParams } from "./public-map-api";

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
});
