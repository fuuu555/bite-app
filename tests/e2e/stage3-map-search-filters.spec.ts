import { expect, test, type Page } from "@playwright/test";

const cuisineId = "99f98e31-1bd4-4149-9822-d66139d16482";

const restaurant = {
  id: "71c352a3-6609-4dc7-9f76-8eb284a874b8",
  name: "公開地圖驗收店家",
  latitude: 24.9537,
  longitude: 121.2258,
  primary_cuisine: {
    id: cuisineId,
    display_name: "台灣料理",
    color: "#F26B4F",
    icon_key: "rice-bowl",
  },
  price_range: "under_200",
  menu_url: null,
};

async function mockMapApis(page: Page, mapRequests: string[]) {
  await page.route("**/api/v1/map/restaurants?*", async (route) => {
    mapRequests.push(route.request().url());
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", restaurants: [] }),
    });
  });
  await page.route("**/api/v1/map/cuisines", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([restaurant.primary_cuisine]),
    });
  });
  await page.route("**/api/v1/map/search?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        locations: [
          {
            label: "中原大學，桃園市中壢區",
            region: "桃園市中壢區",
            latitude: 24.9578,
            longitude: 121.2405,
            source: "geocoding",
          },
        ],
        restaurants: [restaurant],
      }),
    });
  });
}

test("map search separates locations and published restaurants", async ({ page }) => {
  const mapRequests: string[] = [];
  await mockMapApis(page, mapRequests);

  await page.goto("/map");
  const searchbox = page.getByRole("searchbox", { name: "搜尋地區、地址或店家名稱" });
  await searchbox.fill("中原");
  await expect(page.getByRole("heading", { name: "地區／地址" })).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("heading", { name: "已發布店家" })).toBeVisible();
  await expect(page.getByRole("button", { name: /搜尋此區域/ })).toHaveCount(0);
  await expect.poll(() => mapRequests.length).toBe(1);

  await page.getByRole("option", { name: /中原大學/ }).click();
  await expect(page.getByRole("button", { name: "搜尋此區域" })).toBeVisible();
  await expect.poll(() => mapRequests.length).toBe(1);

  await searchbox.fill("公開");
  await expect(page.getByRole("option", { name: /公開地圖驗收店家/ })).toBeVisible({
    timeout: 5_000,
  });
  await page.getByRole("option", { name: /公開地圖驗收店家/ }).click();
  await expect(page.getByRole("heading", { name: "公開地圖驗收店家" })).toBeVisible();
  await expect(page.getByText("台灣料理")).toBeVisible();
});

test("map filters wait for explicit area search and serialize active conditions", async ({
  page,
}) => {
  const mapRequests: string[] = [];
  await mockMapApis(page, mapRequests);

  await page.goto("/map");
  await expect.poll(() => mapRequests.length).toBe(1);

  await page.getByRole("button", { name: /篩選/ }).click();
  await expect(page.getByLabel("地圖篩選條件")).toBeVisible();
  const citySelect = page.getByLabel("縣市");
  const districtSelect = page.getByLabel("行政區");
  await expect(districtSelect).toBeDisabled();
  await citySelect.selectOption({ label: "臺北市" });
  await expect(districtSelect).toBeEnabled();
  await districtSelect.selectOption({ label: "中正區" });
  await citySelect.selectOption({ label: "桃園市" });
  await expect(districtSelect).toHaveValue("");
  await districtSelect.selectOption({ label: "中壢區" });
  await page.getByLabel("$200–400").check();
  await page.getByLabel("台灣料理").check();
  await page.getByRole("button", { name: "套用篩選" }).click();

  const activeFilters = page.getByLabel("目前套用的篩選條件");
  await expect(activeFilters).toContainText("桃園市・中壢區");
  await expect(
    activeFilters.getByRole("button", { name: "移除條件 桃園市・中壢區" }),
  ).toBeVisible();
  await expect.poll(() => mapRequests.length).toBe(1);

  await page.getByRole("button", { name: "搜尋此區域" }).click();
  await expect.poll(() => mapRequests.length).toBe(2);
  const params = new URL(mapRequests[1]).searchParams;
  expect(params.get("city")).toBe("桃園市");
  expect(params.get("district")).toBe("中壢區");
  expect(params.get("price_ranges")).toBe("200_to_400");
  expect(params.get("cuisine_ids")).toBe(cuisineId);
});

test("cluster demo groups ten Zhongyuan restaurants into a numbered marker", async ({ page }) => {
  await page.goto("/map?cluster-demo=1");

  const cluster = page.locator(".public-map-cluster");
  await expect(cluster).toHaveCount(1, { timeout: 15_000 });
  await expect(cluster).toHaveText("10");
  await expect(cluster).toHaveAttribute("aria-label", "10 間店家群聚，點擊放大地圖");
  await cluster.click();
  await expect(page.locator(".public-map-cluster")).toHaveCount(2, { timeout: 5_000 });
});
