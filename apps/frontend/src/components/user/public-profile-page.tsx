"use client";

import { IconArrowLeft, IconMap2, IconTag } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Profile, UserApiError, userApi } from "@/lib/user-api";

export function PublicProfilePage({ userId }: { userId: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    userApi<Profile>(`/profiles/${userId}`)
      .then(setProfile)
      .catch((caught) => {
        setError(
          caught instanceof UserApiError && caught.status === 404
            ? "找不到這個公開個人頁面。"
            : "目前無法載入公開個人頁面。",
        );
      });
  }, [userId]);

  if (error) {
    return (
      <main className="profile-state">
        <p>{error}</p>
        <Link className="button button--secondary" href="/">
          回到探索
        </Link>
      </main>
    );
  }
  if (!profile) {
    return (
      <main className="profile-state is-loading">
        <p>正在載入公開個人頁面…</p>
      </main>
    );
  }

  return (
    <main className="public-profile-page" aria-labelledby="public-profile-title">
      <Link className="back-link" href="/">
        <IconArrowLeft aria-hidden="true" /> 回到探索
      </Link>
      <section className="public-profile-card">
        <div className="public-profile-card__top">
          {profile.avatar_url ? (
            // Remote avatar URLs stay unoptimized until signed object storage is introduced.
            // 遠端頭像網址在導入簽名物件儲存前不交給 Next Image 代理。
            // eslint-disable-next-line @next/next/no-img-element
            <img
              className="profile-avatar"
              src={profile.avatar_url}
              alt={`${profile.display_name} 的頭像`}
            />
          ) : (
            <span className="profile-avatar profile-avatar--fallback" aria-hidden="true">
              {profile.display_name.slice(0, 1)}
            </span>
          )}
          <div>
            <p className="profile-eyebrow">BiteMap / Public profile</p>
            <h1 id="public-profile-title">{profile.display_name}</h1>
            <p>{profile.bio || "這位 BiteMap 使用者還沒有寫下自我介紹。"}</p>
          </div>
        </div>
        <div className="profile-tags" aria-label="美食興趣標籤">
          {profile.tags.map((tag) => (
            <span className="profile-tag" key={tag.id}>
              <IconTag aria-hidden="true" /> {tag.display_name}
            </span>
          ))}
        </div>
        <div className="public-profile-map-note">
          <IconMap2 aria-hidden="true" />
          <div>
            <strong>公開美食內容</strong>
            <p>個人美食地圖的資料來源尚未定案，相關內容會在後續階段加入。</p>
          </div>
        </div>
      </section>
    </main>
  );
}
