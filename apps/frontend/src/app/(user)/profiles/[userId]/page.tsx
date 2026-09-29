import { PublicProfilePage } from "@/components/user/public-profile-page";

export default async function PublicProfileRoute({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return <PublicProfilePage userId={userId} />;
}
