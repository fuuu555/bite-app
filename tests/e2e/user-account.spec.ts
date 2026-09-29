import { expect, test } from "@playwright/test";
import { mockSignedInUser } from "./user-session";

test("未登入先到登入頁，登入頁只提供 Google 登入", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);

  const googleLogin = page.getByRole("link", { name: /使用 Google 登入/ });
  await expect(googleLogin).toHaveAttribute("href", /\/api\/v1\/auth\/google\/start$/);
  await expect(page.getByText("電子郵件")).toHaveCount(0);
  await expect(page.getByText("密碼")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /建立帳號/ })).toHaveCount(0);
});

test("Google callback 錯誤會在登入頁顯示安全提示", async ({ page }) => {
  const loginError = page.locator(".user-auth-feedback");
  await page.goto("/login?error=google_login_failed");
  await expect(loginError).toHaveText("Google 登入沒有完成，請稍後再試。");

  await page.goto("/login?error=account_conflict");
  await expect(loginError).toHaveText(
    "這個 Google 帳戶已經綁定其他一般使用者資料，請使用原本的 Google 帳戶登入。",
  );
});

test("有效的一般使用者 Session 可以進入個人頁", async ({ page }) => {
  await mockSignedInUser(page);
  await page.route("**/api/v1/me/profile", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-4000-8000-000000000001",
        email: "e2e@example.test",
        display_name: "BiteMap 使用者",
        bio: "喜歡探索巷弄小店",
        avatar_url: null,
        tags: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            slug: "甜食控",
            display_name: "甜食控",
            is_system: true,
          },
        ],
      }),
    });
  });
  await page.goto("/profile");
  await expect(page.getByRole("heading", { name: "個人頁面" })).toBeVisible();
  await expect(page.getByText("甜食控")).toBeVisible();
});

test("個人設定新增常用 Tag 會立即顯示回饋", async ({ page }) => {
  await mockSignedInUser(page);
  await page.route("**/api/v1/me/profile", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-4000-8000-000000000001",
        email: "e2e@example.test",
        display_name: "BiteMap 使用者",
        bio: null,
        avatar_url: null,
        tags: [],
      }),
    });
  });
  await page.route("**/api/v1/me/sessions", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.goto("/profile/settings");
  await page.locator(".profile-tag-options button", { hasText: "甜食控" }).click();
  await expect(page.locator(".profile-tag-toast")).toHaveText("已加入「甜食控」，儲存後就會套用。");
  await expect(page.locator(".profile-tag--button.is-new")).toContainText("甜食控");

  const sweetTagOption = page.locator(".profile-tag-options button", { hasText: "甜食控" });
  await sweetTagOption.click();
  await expect(page.locator(".profile-tag-toast")).toHaveText("已移除「甜食控」。");
  await expect(sweetTagOption).toHaveAttribute("aria-pressed", "false");
});
