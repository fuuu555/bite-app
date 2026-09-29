import { expect, test } from "@playwright/test";

import { mockSignedInUser } from "./user-session";

const restaurantId = "71c352a3-6609-4dc7-9f76-8eb284a874b8";

const restaurant = {
  id: restaurantId,
  name: "探索測試店家",
  address: "桃園市中壢區測試路 4 號",
  primary_cuisine: {
    id: "99f98e31-1bd4-4149-9822-d66139d16482",
    display_name: "台灣料理",
    color: "#F26B4F",
    icon_key: "rice-bowl",
  },
  price_range: "200_to_400",
  menu_url: "https://example.test/menu",
  photo_url: "https://example.test/shared-photo.jpg",
  distance_meters: null,
  app: { revisit_rate: null, rating_count: null, trust_level: null },
  google: { rating: null, review_count: null },
};

test("explore skeleton shares results with the restaurant detail route", async ({ page }) => {
  await mockSignedInUser(page);
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation({ latitude: 24.9537, longitude: 121.2258 });

  let exploreRequestUrl = "";
  await page.route("**/api/v1/map/cuisines", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([restaurant.primary_cuisine]),
    });
  });
  await page.route("**/api/v1/explore/restaurants?*", async (route) => {
    exploreRequestUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        query: "骨架",
        sort: "stable",
        top_restaurants: [restaurant],
        restaurants: [restaurant],
      }),
    });
  });
  await page.route(`**/api/v1/explore/restaurants/${restaurantId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...restaurant,
        latitude: 24.9537,
        longitude: 121.2258,
        menu: { url: restaurant.menu_url, last_updated_at: null },
        menus: [],
        photos: [],
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "本週 Top 3 必吃" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "完整搜尋結果" })).toBeVisible();
  await expect(page.locator('img[alt="探索測試店家店家照片"]').first()).toHaveAttribute(
    "src",
    restaurant.photo_url,
  );
  await expect(page.getByLabel("距離")).toBeEnabled();
  await expect(page.getByLabel("距離")).toHaveValue("");

  await page.getByLabel("距離").selectOption("5");
  await page.getByLabel("價格").selectOption("200_to_400");
  await page.getByLabel("料理分類").selectOption(restaurant.primary_cuisine.id);
  await page.getByLabel("餐廳名稱").fill("骨架");
  await page.getByRole("button", { name: "開始探索" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("q")).toBe("骨架");
  await expect.poll(() => new URL(page.url()).searchParams.get("price")).toBe("200_to_400");
  await expect
    .poll(() => new URL(page.url()).searchParams.get("cuisine"))
    .toBe(restaurant.primary_cuisine.id);
  await expect.poll(() => new URL(page.url()).searchParams.get("distance")).toBe("5");
  await expect.poll(() => new URL(exploreRequestUrl).searchParams.get("distance_km")).toBe("5");
  await expect.poll(() => new URL(exploreRequestUrl).searchParams.get("latitude")).toBe("24.9537");
  await expect(page.getByRole("heading", { name: "探索測試店家" }).first()).toBeVisible();
  await page.getByRole("link", { name: "查看餐廳" }).first().click();

  await expect(page).toHaveURL(new RegExp(`/restaurants/${restaurantId}$`));
  await expect(page.locator(".restaurant-detail-v3__carousel img")).toHaveAttribute(
    "src",
    restaurant.photo_url,
  );
  await page.goBack();
  await expect(page.getByLabel("餐廳名稱")).toHaveValue("骨架");
  await expect(page.getByLabel("價格")).toHaveValue("200_to_400");
  await expect(page.getByLabel("料理分類")).toHaveValue(restaurant.primary_cuisine.id);
  await expect(page.getByLabel("距離")).toHaveValue("5");
  await page.getByRole("link", { name: "查看餐廳" }).first().click();
  await expect(page.getByRole("heading", { name: "快速資訊" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Google 資料" })).toBeVisible();
  await expect(page.getByRole("link", { name: /餐廳菜單/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "更多資訊" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "App 資料" })).toHaveCount(0);
  await expect(page.getByText("評論可信度")).toHaveCount(0);
  await expect(page.getByText("Google 評分")).toBeVisible();
  await expect(page.getByText("尚未接入").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "收藏" })).toBeDisabled();
});
