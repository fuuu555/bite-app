import { expect, test } from "@playwright/test";

import { mockSignedInUser } from "./user-session";

test("旅客可以從找住宿快捷鍵取得觀光署旅宿推薦", async ({ page }) => {
  await mockSignedInUser(page);
  await page.route("**/api/v1/itinerary/plan", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "rules",
        title: "附近住宿推薦",
        summary: "智慧推薦只使用觀光署旅館民宿資料，整理出 1 個附近選項。",
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
        stops: [
          {
            order: 1,
            role: "lodging",
            reason: "使用觀光署旅館民宿資料，距離目前位置較近。",
            suggested_duration_minutes: 480,
            place: {
              id: "tourism-hotel-1",
              source: "tourism",
              source_dataset: "hotel",
              source_record_id: "hotel-1",
              category: "hotel",
              name: "觀光署測試旅館",
              address: "台北市中正區測試路 1 號",
              latitude: 25.038,
              longitude: 121.564,
              distance_meters: 320,
              description: null,
              phone: null,
              official_url: null,
              opening_hours: null,
              source_updated_at: null,
              tags: [],
              cuisine_name: null,
              price_range: null,
              icon_color: "#8B6BB1",
            },
          },
        ],
        alternatives: [],
      }),
    });
  });

  await page.goto("/travel");
  await expect(page.getByRole("heading", { name: /從現在的位置/ })).toBeVisible();
  await page.getByRole("button", { name: "找住宿" }).click();
  await expect(page.getByRole("heading", { name: "附近住宿推薦" })).toBeVisible();
  await expect(page.getByText("觀光署旅館民宿資料").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "觀光署測試旅館" })).toBeVisible();
});
