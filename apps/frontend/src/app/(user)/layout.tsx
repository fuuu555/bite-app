import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { MealDraftBar } from "@/features/meals/components/meal-draft-bar";
import { UserAppGate } from "@/shared/auth/user-app-gate";
import { UserFooterNav } from "@/shared/ui/user-footer-nav";
import { RealtimeProvider } from "@/shared/realtime/realtime";

export default async function UserLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get("bitemap_user_session")) {
    redirect("/login");
  }

  return (
    <div className="user-app-shell">
      <UserAppGate>
        <RealtimeProvider>
          <div className="user-app-content">{children}</div>
          <MealDraftBar />
          <UserFooterNav />
        </RealtimeProvider>
      </UserAppGate>
    </div>
  );
}
