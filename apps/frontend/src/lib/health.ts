export type ApiReadiness = {
  status: "ready" | "unavailable";
  postgis?: string;
  detail?: string;
};

export async function getApiReadiness(apiBaseUrl: string): Promise<ApiReadiness> {
  try {
    const response = await fetch(`${apiBaseUrl}/health/ready`, { cache: "no-store" });
    const payload = (await response.json().catch(() => ({}))) as {
      postgis?: unknown;
      detail?: unknown;
    };

    if (!response.ok) {
      return { status: "unavailable", detail: "API 尚未啟動" };
    }

    return {
      status: "ready",
      postgis: typeof payload.postgis === "string" ? payload.postgis : "PostGIS ready",
      detail: "API 與資料庫已連線",
    };
  } catch {
    return { status: "unavailable", detail: "API 尚未啟動" };
  }
}
