import { describe, expect, it, vi } from "vitest";
import { getApiReadiness } from "./health";

describe("getApiReadiness", () => {
  it("returns PostGIS status for a healthy API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ postgis: "3.5.3" }), { status: 200 }),
      ),
    );

    await expect(getApiReadiness("http://localhost:8000")).resolves.toEqual({
      status: "ready",
      postgis: "3.5.3",
      detail: "API 與資料庫已連線",
    });
  });

  it("fails softly while the API is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(getApiReadiness("http://localhost:8000")).resolves.toEqual({
      status: "unavailable",
      detail: "API 尚未啟動",
    });
  });
});
