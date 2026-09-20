/** API readiness result / API readiness 檢查結果。 */
export type ApiReadiness = {
  status: "ready" | "unavailable";
  postgis?: string;
  detail?: string;
};

export async function getApiReadiness(apiBaseUrl: string): Promise<ApiReadiness> {
  try {
    // Disable caching so the status reflects the current backend process.
    // 關閉快取，確保畫面反映目前後端程序的狀態。
    const response = await fetch(`${apiBaseUrl}/health/ready`, { cache: "no-store" });
    const payload = (await response.json().catch(() => ({}))) as {
      postgis?: unknown;
      detail?: unknown;
    };

    if (!response.ok) {
      // Keep the homepage usable while the API is still starting.
      // API 啟動中時，首頁仍可顯示，而不是整頁失敗。
      return { status: "unavailable", detail: "API 尚未啟動" };
    }

    return {
      status: "ready",
      postgis: typeof payload.postgis === "string" ? payload.postgis : "PostGIS ready",
      detail: "API 與資料庫已連線",
    };
  } catch {
    // Network errors are expected during local startup and are handled gracefully.
    // 本機啟動初期可能發生網路錯誤，這裡以可理解的狀態處理。
    return { status: "unavailable", detail: "API 尚未啟動" };
  }
}
