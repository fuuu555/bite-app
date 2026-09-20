// Shown while the server component is waiting for the API status.
// Server Component 等待 API 狀態時顯示此 loading UI。
export default function Loading() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 items-center px-6 py-12 sm:px-10">
      <p className="text-slate-500">正在檢查 BiteMap 服務狀態…</p>
    </main>
  );
}
