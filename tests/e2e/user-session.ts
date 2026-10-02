import type { Page } from "@playwright/test";

export async function mockSignedInUser(page: Page, options: { mockRealtime?: boolean } = {}) {
  // Pair the browser cookie with a scoped identity response so protected pages exercise their real gate.
  // 同時提供瀏覽器 Cookie 與限定範圍的身分回應，讓受保護頁面走過真正的登入守門流程。
  await page.context().addCookies([
    {
      name: "bitemap_user_session",
      value: "e2e-session",
      url: "http://localhost:3000",
    },
  ]);
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-4000-8000-000000000001",
        email: "e2e@example.test",
        role: "user",
      }),
    });
  });
  if (options.mockRealtime !== false) {
    // Signed-in UI tests use a fake session, so keep the shared socket deterministic too.
    // 已登入 UI 測試使用假 Session，共用 WebSocket 也一併隔離，避免持續打到真後端重連。
    await page.routeWebSocket(/\/api\/v1\/ws$/, (socket) => {
      socket.send(JSON.stringify({ type: "ready" }));
    });
  }
}
