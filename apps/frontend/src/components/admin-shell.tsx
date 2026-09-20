"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { AdminApiError, adminApi } from "@/lib/admin-api";

type AdminUser = { id: string; email: string; role: string };

const navigation = [
  { href: "/admin/restaurants", label: "店家管理", icon: "restaurant" as const },
  { href: "/admin/cuisines", label: "料理分類", icon: "cuisine" as const },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi<AdminUser>("/me")
      .then(setUser)
      .catch((error: unknown) => {
        if (error instanceof AdminApiError && error.status === 401) {
          router.replace("/admin/login");
        }
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function logout() {
    await adminApi<void>("/session", { method: "DELETE" });
    router.replace("/admin/login");
  }

  if (loading || !user) {
    return (
      <main className="admin-loading" aria-busy="true" aria-label="載入管理介面">
        <div className="admin-loading__mark" />
        <div className="admin-loading__line" />
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
