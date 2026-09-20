import { expect, test } from "@playwright/test";

test("administrator can sign in and create a cuisine", async ({ page }, testInfo) => {
  const email = process.env.E2E_ADMIN_EMAIL ?? "stage1-e2e@example.test";
  const password = process.env.E2E_ADMIN_PASSWORD ?? "stage1-e2e-password";
  const projectSlug = testInfo.project.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const timestamp = Date.now();
  const uniqueSlug = `e2e-${projectSlug}-${timestamp}`;
  const cuisineName = `E2E 台灣料理 ${projectSlug}-${timestamp}`;
  const restaurantName = `E2E 測試店 ${projectSlug}-${timestamp}`;

  try {
    await page.goto("/admin/login");
    await page.getByLabel("電子郵件").fill(email);
    await page.getByLabel("密碼").fill(password);
    await page.getByRole("button", { name: "登入管理後台" }).click();

    await expect(page.getByRole("heading", { name: "店家管理" })).toBeVisible();
    await page.goto("/admin/cuisines");
    await expect(page.getByRole("heading", { name: "料理分類" })).toBeVisible();

    await page.getByLabel("顯示名稱", { exact: true }).fill(cuisineName);
    await expect(page.getByLabel("系統識別碼")).toHaveValue(uniqueSlug);
    await page.getByRole("button", { name: "新增料理分類" }).click();

    await expect(page.getByText(cuisineName)).toBeVisible();
    await expect(page.getByText(new RegExp(uniqueSlug))).toBeVisible();

    await page.goto("/admin/restaurants/new");
    await page.getByLabel("店家名稱").fill(restaurantName);
    await page.getByLabel("地址").fill("台北市中正區忠孝西路一段 49 號");
    await page.getByLabel("菜單網址（可選）").fill(`https://example.test/menu/${uniqueSlug}`);
    await page.getByLabel("主要料理").selectOption({ label: cuisineName });
    await page.getByLabel("價格區間").selectOption("200_to_400");

    const map = page.getByLabel("店家座標地圖");
    await expect(map).toBeVisible();
    await map.click({ position: { x: 220, y: 150 } });
    await expect(page.getByText(/^緯度 (?!尚未設定)/)).toBeVisible();

    const marker = page.locator(".maplibregl-marker");
    await expect(marker).toBeVisible();
    const markerBox = await marker.boundingBox();
    if (!markerBox) throw new Error("map marker has no bounding box");
    await page.mouse.move(markerBox.x + markerBox.width / 2, markerBox.y + markerBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(markerBox.x + markerBox.width / 2 + 24, markerBox.y + markerBox.height / 2);
    await page.mouse.up();

    await page.getByRole("button", { name: "發布店家" }).click();
    await page.goto("/admin/restaurants");
    const restaurantRow = page.getByRole("row", { name: new RegExp(restaurantName) });
    await expect(restaurantRow).toContainText("已發布", { timeout: 15_000 });
    await expect(page.locator(`a[href="https://example.test/menu/${uniqueSlug}"]`)).toBeVisible();
    await page.getByLabel("地區／地址").fill("中正區");
    await expect(page.locator(`a[href="https://example.test/menu/${uniqueSlug}"]`)).toBeVisible();
  } finally {
    const restaurantsResponse = await page.request.get("/api/v1/admin/restaurants");
    if (restaurantsResponse.ok()) {
      const restaurants = (await restaurantsResponse.json()) as Array<{ id: string; name: string }>;
      const restaurant = restaurants.find((item) => item.name === restaurantName);
      if (restaurant) await page.request.delete(`/api/v1/admin/restaurants/${restaurant.id}`);
    }

    const cuisinesResponse = await page.request.get("/api/v1/admin/cuisines");
    if (cuisinesResponse.ok()) {
      const cuisines = (await cuisinesResponse.json()) as Array<{ id: string; slug: string }>;
      const cuisine = cuisines.find((item) => item.slug === uniqueSlug);
      if (cuisine) await page.request.delete(`/api/v1/admin/cuisines/${cuisine.id}`);
    }
    await page.request.delete("/api/v1/admin/session");
  }
});
