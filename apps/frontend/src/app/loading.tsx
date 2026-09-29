// Shared fallback shown while a route is preparing its content.
// 路由準備內容時共用的載入提示。
export default function Loading() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 items-center px-6 py-12 sm:px-10">
      <p className="text-slate-500">正在載入 BiteMap…</p>
    </main>
  );
}
