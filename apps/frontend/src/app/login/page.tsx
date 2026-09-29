import { UserAuthForm } from "@/components/user/user-auth-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;
  return <UserAuthForm error={params.error} />;
}
