import { expect, test } from "@playwright/test";

import { mockSignedInUser } from "./user-session";

test("explore skeleton keeps the primary navigation", async ({ page }) => {
  await mockSignedInUser(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "今天想吃什麼？" })).toBeVisible();
  await expect(page.getByRole("link", { name: "地圖找店" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "主要功能" })).toBeVisible();
  await expect(page.getByRole("link", { name: "探索" })).toHaveAttribute("aria-current", "page");
});
