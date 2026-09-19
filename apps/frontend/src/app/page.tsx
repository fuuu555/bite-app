import { getApiReadiness } from "@/lib/health";

export const dynamic = "force-dynamic";

export default async function Home() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const readiness = await getApiReadiness(apiBaseUrl);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-6 py-12 sm:px-10">
      <header className="flex flex-col gap-4">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-orange-600">
          Stage 0 · 基礎環境
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-slate-950 sm:text-6xl">
          BiteMap
        </h1>
        <p className="max-w-2xl text-lg leading-8 text-slate-600">
          先把地圖探索需要的前後端、資料庫與健康檢查接通，再逐步加入店家與聚合功能。
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2" aria-label="服務狀態">
        <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">FastAPI</p>
          <p className="mt-3 text-2xl font-semibold text-slate-950">
            {readiness.status === "ready" ? "已連線" : "尚未就緒"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {readiness.detail ?? "API readiness endpoint"}
          </p>
        </article>
        <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">PostgreSQL + PostGIS</p>
          <p className="mt-3 text-2xl font-semibold text-slate-950">
            {readiness.postgis ?? "等待資料庫"}
          </p>
          <p className="mt-2 text-sm text-slate-500">地理資料與店家搜尋的 Stage 0 基礎。</p>
        </article>
      </section>
    </main>
  );
}
