import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import path from "node:path";

// Keep one root .env for the frontend and backend in this monorepo.
// 此 monorepo 的前後端共用根目錄 .env，避免維護兩份設定。
loadEnvConfig(path.resolve(process.cwd(), "../.."));

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Playwright uses 127.0.0.1 during local E2E runs.
  // Playwright 本機 E2E 測試使用 127.0.0.1，因此允許此開發來源。
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    // Keep browser requests same-origin so authentication cookies work reliably.
    // 瀏覽器只連前端同源路徑，再由 Next.js 轉送 API，確保登入 Cookie 穩定送出。
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
