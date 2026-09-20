import { expect, test } from "@playwright/test";

test("public map supports manual area search and restaurant preview", async ({ page }) => {
  let mapRequestCount = 0;
  await page.route("**/api/v1/map/restaurants?*", async (route) => {
    mapRequestCount += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        restaurants: [
          {
            id: "71c352a3-6609-4dc7-9f76-8eb284a874b8",
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

  await page.goto("/map");
  const map = page.getByLabel("公開店家地圖");
  await expect(map).toBeVisible();
  await expect(page.getByText(/定位未開啟/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: /公開地圖驗收店家/ })).toBeVisible({
    timeout: 15_000,
  });

  const mapBox = await map.boundingBox();
  if (!mapBox) throw new Error("public map has no bounding box");
  await page.mouse.move(mapBox.x + mapBox.width * 0.65, mapBox.y + mapBox.height * 0.45);
  await page.mouse.down();
  await page.mouse.move(mapBox.x + mapBox.width * 0.45, mapBox.y + mapBox.height * 0.45, {
    steps: 5,
  });
  await page.mouse.up();

  await page.getByRole("button", { name: "搜尋此區域" }).click();
  await expect.poll(() => mapRequestCount).toBeGreaterThanOrEqual(2);

  await page.getByRole("button", { name: /公開地圖驗收店家/ }).click();
  await expect(page.getByRole("heading", { name: "公開地圖驗收店家" })).toBeVisible();
  await expect(page.getByText("台灣料理")).toBeVisible();

  await page.getByRole("link", { name: "約飯" }).click();
  await expect(page.getByRole("heading", { name: "約飯功能準備中" })).toBeVisible();
});
