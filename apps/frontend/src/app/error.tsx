"use client";

// Client boundary provides a retry action for unexpected render failures.
// Client boundary 提供非預期渲染錯誤的重試操作。
export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-start gap-4 px-6 py-12 sm:px-10">
      <h1 className="text-2xl font-semibold text-slate-950">頁面載入失敗</h1>
      <p className="text-slate-600">請重試；若 API 尚未啟動，首頁會顯示服務尚未就緒。</p>
      <button
        type="button"
        onClick={() => reset()}
        className="rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white"
      >
        重試
      </button>
    </main>
  );
}
