import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchItineraryPlan, type ItineraryPlanRequest } from "./itinerary-api";

describe("itinerary API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts a grounded travel request", async () => {
    const payload: ItineraryPlanRequest = {
      latitude: 25.0375,
      longitude: 121.5637,
      quick_action: "stay",
      duration: "half_day",
      radius_km: 5,
      transport: "public_transport",
      interests: [],
      include_lodging: true,
    };
    const responseBody = {
      source: "rules",
      title: "附近住宿推薦",
      summary: "只使用官方旅宿資料。",
      center_latitude: 25.0375,
      center_longitude: 121.5637,
      city: "台北市",
      radius_km: 5,
      intent: {
        city: "台北市",
        duration: "half_day",
        transport: "public_transport",
        interests: [],
        meal_preference: null,
        include_lodging: true,
      },
      stops: [],
      alternatives: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchItineraryPlan(payload)).resolves.toEqual(responseBody);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/itinerary/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
      signal: undefined,
    });
  });

  it("surfaces a server error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "請選擇縣市或開啟定位。" }), { status: 422 }),
      ),
    );

    await expect(
      fetchItineraryPlan({
        quick_action: "plan",
        duration: "half_day",
        radius_km: 5,
        transport: "public_transport",
        interests: [],
        include_lodging: false,
      }),
    ).rejects.toMatchObject({ status: 422, message: "請選擇縣市或開啟定位。" });
  });
});
