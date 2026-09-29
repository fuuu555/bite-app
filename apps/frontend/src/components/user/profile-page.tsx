"use client";

import {
  IconBookmark,
  IconChevronRight,
  IconHeart,
  IconMap2,
  IconMessageCircle,
  IconSettings,
  IconTag,
  IconUser,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MyProfile, UserApiError, userApi } from "@/lib/user-api";

function ProfileAvatar({ profile }: { profile: Pick<MyProfile, "avatar_url" | "display_name"> }) {
  return profile.avatar_url ? (
    // Keep avatar rendering URL-based until signed object-storage uploads are available.
    // 簽名物件儲存上傳完成前，頭像維持使用可驗證的 URL。
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
  );
}

export function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    userApi<MyProfile>("/me/profile")
      .then(setProfile)
      .catch((caught) => {
        if (caught instanceof UserApiError && caught.status === 401) {
          router.replace("/login");
          return;
        }
        setError("目前無法載入個人頁面，請稍後再試。");
      });
  }, [router]);

  if (error) {
    return <ProfileState message={error} />;
  }
  if (!profile) {
    return <ProfileState message="正在整理你的 BiteMap 個人頁面…" loading />;
  }

  return (
    <main className="profile-page" aria-labelledby="profile-title">
      <header className="profile-page__header">
        <div>
          <p className="profile-eyebrow">BiteMap / Profile</p>
          <h1 id="profile-title">個人頁面</h1>
          <p>記錄我吃過的味道，也遇見更多喜歡的日常。</p>
        </div>
        <Link className="button button--secondary" href="/profile/settings">
          <IconSettings aria-hidden="true" />
          編輯個人資料
        </Link>
      </header>

      <section className="profile-layout">
        <aside className="profile-card">
          <div className="profile-card__identity">
            <ProfileAvatar profile={profile} />
            <div>
              <h2>{profile.display_name}</h2>
              <p>{profile.bio || "還沒有寫下自我介紹。"}</p>
            </div>
          </div>
          <div className="profile-tags" aria-label="美食興趣標籤">
            {profile.tags.length > 0 ? (
              profile.tags.map((tag) => (
                <span className="profile-tag" key={tag.id}>
                  <IconTag aria-hidden="true" /> {tag.display_name}
                </span>
              ))
            ) : (
              <span className="profile-empty-tag">新增幾個 Tag，讓大家更快認識你的口味。</span>
            )}
          </div>
          <div className="profile-card__note">
            <IconHeart aria-hidden="true" />
            <span>你的美食紀錄會在後續階段逐步加入。</span>
          </div>
        </aside>

        <section className="profile-content-card">
          <nav className="profile-tabs" aria-label="個人內容分類">
            <span className="is-active">公開資料</span>
            <span className="is-disabled">美食留言</span>
            <span className="is-disabled">收藏</span>
          </nav>
          <div className="profile-content-grid">
            <div className="profile-section-copy">
              <div className="profile-section-title">
                <IconUser aria-hidden="true" />
                <h2>關於我</h2>
              </div>
              <p>{profile.bio || "在個人設定寫下你的口味，讓之後的約飯與社交入口更有你的樣子。"}</p>
              <Link className="text-link" href="/profile/settings">
                編輯公開資料 <IconChevronRight aria-hidden="true" />
              </Link>
            </div>
            <div className="profile-map-placeholder">
              <div className="profile-section-title">
                <IconMap2 aria-hidden="true" />
                <h2>我的美食地圖</h2>
              </div>
              <div className="profile-map-placeholder__art" aria-hidden="true">
                <span className="profile-map-pin profile-map-pin--one" />
                <span className="profile-map-pin profile-map-pin--two" />
                <span className="profile-map-pin profile-map-pin--three" />
              </div>
              <p>個人美食地圖的資料來源尚未定案，先保留這個入口。</p>
            </div>
          </div>
          <div className="profile-future-links">
            <span>
              <IconMessageCircle aria-hidden="true" /> 美食留言功能準備中
            </span>
            <span>
              <IconBookmark aria-hidden="true" /> 收藏列表功能準備中
            </span>
          </div>
        </section>
      </section>
    </main>
  );
}

function ProfileState({ message, loading = false }: { message: string; loading?: boolean }) {
  return (
    <main className={`profile-state${loading ? " is-loading" : ""}`}>
      <span className="profile-state__mark">B</span>
      <p>{message}</p>
    </main>
  );
}
