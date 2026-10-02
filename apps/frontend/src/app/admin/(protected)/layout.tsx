import { AdminShell } from "@/features/admin/components/admin-shell";

export default function ProtectedAdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
