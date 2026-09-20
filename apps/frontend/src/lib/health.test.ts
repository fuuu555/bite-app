/** Client-side health helper tests / 前端健康檢查 helper 測試。 */
import { describe, expect, it, vi } from "vitest";
import { getApiReadiness } from "./health";

describe("getApiReadiness", () => {
  it("returns PostGIS status for a healthy API", async () => {
    // Simulate the API response without requiring a running server.
    // 模擬 API 回應，不依賴實際啟動的伺服器。
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ postgis: "3.5.3" }), { status: 200 })),
    );

    await expect(getApiReadiness("http://localhost:8000")).resolves.toEqual({
      status: "ready",
      postgis: "3.5.3",
      detail: "API 與資料庫已連線",
    });
  });

  it("fails softly while the API is offline", async () => {
    // Offline startup should produce a safe UI state instead of throwing.
    // API 尚未啟動時應回傳安全狀態，而不是拋出例外。
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(getApiReadiness("http://localhost:8000")).resolves.toEqual({
      status: "unavailable",
      detail: "API 尚未啟動",
    });
  });
});
