import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { UserAppGate } from "@/components/user/user-app-gate";
import { UserFooterNav } from "@/components/user/user-footer-nav";

export default async function UserLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get("bitemap_user_session")) {
    redirect("/login");
  }

  return (
    <div className="user-app-shell">
      <UserAppGate>
        <div className="user-app-content">{children}</div>
        <UserFooterNav />
      </UserAppGate>
    </div>
  );
}
