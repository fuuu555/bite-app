"use client";

import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

export function UserAppGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Verify the HttpOnly session before rendering protected client content and preserve the return path.
    // 顯示受保護內容前先驗證 HttpOnly Session，未登入時保留原路徑供登入後返回。
    let active = true;
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((response) => {
        if (!response.ok) {
          throw new Error("authentication required");
        }
        if (active) setReady(true);
      })
      .catch(() => {
        if (active) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        }
      });
    return () => {
      // Ignore a late response after navigation so it cannot update an unmounted gate.
      // 路由切換後忽略延遲回應，避免更新已卸載的登入守門元件。
      active = false;
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <main className="user-app-gate" aria-live="polite">
        <div className="profile-state">
          <span className="profile-state__mark" aria-hidden="true">
            B
          </span>
          <strong>正在確認登入狀態…</strong>
        </div>
      </main>
    );
  }

  return children;
}
