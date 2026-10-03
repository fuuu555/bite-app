import { expect, test } from "@playwright/test";

import { mockSignedInUser } from "./user-session";

const restaurantId = "71c352a3-6609-4dc7-9f76-8eb284a874b8";
const restaurantDetail = {
  id: restaurantId,
  name: "公開地圖驗收店家",
  address: "桃園市中壢區測試路 2 號",
  primary_cuisine: {
    id: "99f98e31-1bd4-4149-9822-d66139d16482",
    display_name: "台灣料理",
    color: "#F26B4F",
    icon_key: "rice-bowl",
  },
  price_range: "under_200",
  menu_url: null,
  app: { revisit_rate: null, rating_count: null, trust_level: null },
  google: { rating: null, review_count: null },
  latitude: 24.9537,
  longitude: 121.2258,
  menu: { url: null, last_updated_at: null },
  menus: [],
  photos: [],
};

test("public map auto-refreshes after moving and opens a restaurant preview", async ({ page }) => {
  await mockSignedInUser(page);
  let mapRequestCount = 0;
  await page.route("**/api/v1/map/restaurants?*", async (route) => {
    mapRequestCount += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        restaurants: [
          {
            id: restaurantId,
            name: "公開地圖驗收店家",
            latitude: 24.9537,
            longitude: 121.2258,
            primary_cuisine: {
              id: "99f98e31-1bd4-4149-9822-d66139d16482",
              display_name: "台灣料理",
              color: "#F26B4F",
              icon_key: "rice-bowl",
            },
            price_range: "under_200",
            menu_url: null,
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/tourism/places?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ places: [], has_more: false }),
    });
  });
  await page.route(`**/api/v1/explore/restaurants/${restaurantId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(restaurantDetail),
    });
  });

  await page.goto("/map");
  const map = page.getByLabel("公開店家地圖");
  await expect(map).toBeVisible();
  await expect(page.locator(".public-map-brand")).toHaveCount(0);
  await expect(page.getByText(/定位未開啟/)).toBeVisible({ timeout: 10_000 });
  const restaurantResult = page
    .locator(".public-map-result")
    .filter({ hasText: "公開地圖驗收店家" });
  const isDesktop = (page.viewportSize()?.width ?? 0) >= 1024;
  if (isDesktop) {
    await expect(restaurantResult).toBeVisible({ timeout: 15_000 });
  } else {
    await expect(page.locator(".public-map-results")).toHaveCSS("display", "none");
    await expect(page.getByText(/找到 1 間 BiteMap 店家/)).toBeVisible({ timeout: 15_000 });
  }

  if (isDesktop) {
    await restaurantResult.click();
    await expect(page.getByRole("heading", { name: "公開地圖驗收店家" })).toBeVisible();
    await expect(page.locator(".restaurant-preview").getByText("台灣料理")).toBeVisible();
    await expect(page.getByRole("button", { name: "搜尋此區域" })).toHaveCount(0);

    await page.getByRole("link", { name: "查看餐廳" }).click();
    await expect(page).toHaveURL(/\/restaurants\/71c352a3-6609-4dc7-9f76-8eb284a874b8$/);
    await expect(page.getByRole("heading", { name: "公開地圖驗收店家" })).toBeVisible();
    await page.getByRole("link", { name: "回到地圖" }).click();
    await expect(page).toHaveURL(/\/map$/);

    const mapBox = await map.boundingBox();
    if (!mapBox) throw new Error("public map has no bounding box");
    const requestsBeforeDrag = mapRequestCount;
    await page.mouse.move(mapBox.x + mapBox.width * 0.65, mapBox.y + mapBox.height * 0.45);
    await page.mouse.down();
    await page.mouse.move(mapBox.x + mapBox.width * 0.45, mapBox.y + mapBox.height * 0.45, {
      steps: 5,
    });
    await page.mouse.up();

    await expect.poll(() => mapRequestCount).toBeGreaterThan(requestsBeforeDrag);
    await expect(page.getByRole("button", { name: "搜尋此區域" })).toHaveCount(0);
  }

  await page.getByRole("link", { name: "約飯" }).click();
  await expect(page.locator(".meals-page__header")).toBeVisible();

  const originalViewport = page.viewportSize();
  if (!originalViewport) throw new Error("browser viewport is unavailable");
  await page.setViewportSize({ width: 1023, height: originalViewport.height });
  await page.goto("/map");
  await expect(page.locator(".public-map-results")).toHaveCSS("display", "none");
  await page.setViewportSize({ width: 1024, height: originalViewport.height });
  await page.goto("/map");
  await expect(page.locator(".public-map-results")).toHaveCSS("display", "flex");
});

test("public map keeps its existing results after an API failure", async ({ page }) => {
  await mockSignedInUser(page);
  let mapRequestCount = 0;
  await page.route("**/api/v1/map/restaurants?*", async (route) => {
    mapRequestCount += 1;
    if (mapRequestCount === 1) {
      await route.abort("failed");
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", restaurants: [] }),
    });
  });

  await page.goto("/map");
  await expect(page.getByText(/店家資料載入失敗/)).toBeVisible({ timeout: 15_000 });
  const map = page.getByLabel("公開店家地圖");
  const mapBox = await map.boundingBox();
  if (!mapBox) throw new Error("public map has no bounding box");
  await page.mouse.move(mapBox.x + mapBox.width * 0.65, mapBox.y + mapBox.height * 0.45);
  await page.mouse.down();
  await page.mouse.move(mapBox.x + mapBox.width * 0.45, mapBox.y + mapBox.height * 0.45, {
    steps: 5,
  });
  await page.mouse.up();
  await expect.poll(() => mapRequestCount).toBeGreaterThanOrEqual(2);
  await expect(page.getByText("這個區域目前沒有已發布店家。")).toBeVisible();
});
