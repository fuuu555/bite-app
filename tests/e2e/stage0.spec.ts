import { expect, test } from "@playwright/test";

test("user homepage links to the public map", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "探索功能準備中" })).toBeVisible();
  await expect(page.getByRole("link", { name: "開啟地圖" })).toHaveAttribute("href", "/map");
  await expect(page.getByRole("navigation", { name: "主要功能" })).toBeVisible();
  await expect(page.getByRole("link", { name: "探索" })).toHaveAttribute("aria-current", "page");
});
