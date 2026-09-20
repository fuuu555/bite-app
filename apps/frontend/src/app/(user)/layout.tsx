import type { ReactNode } from "react";

import { UserFooterNav } from "@/components/user-footer-nav";

export default function UserLayout({ children }: { children: ReactNode }) {
  return (
    <div className="user-app-shell">
      <div className="user-app-content">{children}</div>
      <UserFooterNav />
    </div>
  );
}
