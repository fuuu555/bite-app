"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon } from "@/features/admin/components/icons";
import { AdminApiError, adminApi } from "@/features/admin/api/admin-api";

type AdminUser = { id: string; email: string; role: string };

const navigation = [
  { href: "/admin/restaurants", label: "店家管理", icon: "restaurant" as const },
  { href: "/admin/cuisines", label: "料理分類", icon: "cuisine" as const },
  { href: "/admin/avatars", label: "頭貼資產", icon: "user" as const },
  { href: "/admin/monitoring", label: "系統監控", icon: "monitor" as const },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;
    adminApi<AdminUser>("/me")
      .then((loadedUser) => {
        if (active) setUser(loadedUser);
      })
      .catch((error: unknown) => {
        if (error instanceof AdminApiError && error.status === 401) {
          router.replace("/admin/login");
          return;
        }
        if (!active) return;
        setUser(null);
        setAuthError("管理介面暫時無法驗證身分，請確認後端服務後再試一次。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [retryCount, router]);

  async function logout() {
    await adminApi<void>("/session", { method: "DELETE" });
    router.replace("/admin/login");
  }

  if (loading) {
    return (
      <main className="admin-loading" aria-busy="true" aria-label="載入管理介面">
        <div className="admin-loading__mark" />
        <div className="admin-loading__line" />
      </main>
    );
  }

  if (!user) {
    return (
      <main className="admin-loading admin-loading--error" role="alert">
        <h1>管理介面暫時無法載入</h1>
        <p>{authError || "目前無法確認管理員身分。"}</p>
        <div>
          <button
            type="button"
            className="button button--primary"
            onClick={() => {
              setLoading(true);
              setAuthError("");
              setRetryCount((current) => current + 1);
            }}
          >
            重試
          </button>
          <Link className="button button--secondary" href="/admin/login">
            前往管理員登入
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <Link href="/admin/restaurants" className="admin-brand" aria-label="BiteMap 管理後台">
          <span className="admin-brand__mark">B</span>
          <span>
            <strong>BiteMap</strong>
            <small>管理後台</small>
          </span>
        </Link>
        <nav className="admin-nav" aria-label="管理功能">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname.startsWith(item.href) ? "is-active" : undefined}
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
          <Link
            href="/map?cluster-demo=1"
            className="admin-nav__quick-link"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="map" />
            群聚展示
          </Link>
        </nav>
        <div className="admin-account">
          <span title={user.email}>{user.email}</span>
          <button type="button" onClick={logout} aria-label="登出">
            <Icon name="logout" />
          </button>
        </div>
      </aside>
      <div className="admin-workspace">{children}</div>
    </div>
  );
}
