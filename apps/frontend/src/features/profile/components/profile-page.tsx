"use client";

import {
  IconBookmark,
  IconBuildingStore,
  IconChevronRight,
  IconLogout,
  IconMap2,
  IconMessageCircle,
  IconSettings,
  IconTag,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MyProfile, UserApiError, userApi } from "@/shared/auth/user-api";
import { FoodMapPanel } from "@/features/profile/components/food-map-panel";
import {
  FavoriteRestaurant,
  fetchMyFavorites,
  fetchMyReviews,
  ProfileReview,
  ReviewsApiError,
} from "@/features/restaurants/api/reviews-api";

type ProfileTab = "food-map" | "reviews" | "favorites";

function ProfileAvatar({ profile }: { profile: Pick<MyProfile, "avatar_url" | "display_name"> }) {
  return profile.avatar_url ? (
    // Local assets and external Google URLs both resolve through the same public field.
    // 本地資產與 Google 頭像 URL 都透過同一個公開欄位顯示。
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

function reviewStatusLabel(status: ProfileReview["revisit_status"]) {
  if (status === "will_return") return "會再訪";
  if (status === "will_not_return") return "不會再訪";
  return "普通";
}

function formatReviewDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(new Date(value));
}

function ProfileReviewRow({ review }: { review: ProfileReview }) {
  return (
    <Link className="profile-review-row" href={`/restaurants/${review.restaurant_id}`}>
      {review.restaurant_photo_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={review.restaurant_photo_url} alt="" />
      ) : (
        <span className="profile-review-row__placeholder" aria-hidden="true">
          {review.restaurant_name.slice(0, 1)}
        </span>
      )}
      <span className="profile-review-row__content">
        <span className="profile-review-row__heading">
          <strong>{review.restaurant_name}</strong>
          <small>{formatReviewDate(review.updated_at)}</small>
        </span>
        <span className="profile-review-row__text">{review.content}</span>
        <span className="profile-review-row__meta">
          <span className={`review-status is-${review.revisit_status}`}>
            {reviewStatusLabel(review.revisit_status)}
          </span>
          {review.is_revisit ? `第 ${review.entry_number} 次留言` : "第一次留言"}
          {review.revisit_count > 1 ? ` · 共 ${review.revisit_count} 次` : ""}
          {review.is_edited ? " · 已編輯" : ""}
        </span>
      </span>
      <IconChevronRight aria-hidden="true" />
    </Link>
  );
}

function FavoriteRow({ restaurant }: { restaurant: FavoriteRestaurant }) {
  return (
    <Link className="profile-favorite-row" href={`/restaurants/${restaurant.id}`}>
      <span
        className="profile-favorite-row__marker"
        style={{ backgroundColor: restaurant.primary_cuisine.color }}
      />
      <span>
        <strong>{restaurant.name}</strong>
        <small>
          {restaurant.primary_cuisine.display_name} · {restaurant.address}
        </small>
      </span>
      <IconChevronRight aria-hidden="true" />
    </Link>
  );
}

export function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [favorites, setFavorites] = useState<FavoriteRestaurant[]>([]);
  const [reviews, setReviews] = useState<ProfileReview[]>([]);
  const [tab, setTab] = useState<ProfileTab>("food-map");
  const [error, setError] = useState("");
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    Promise.all([userApi<MyProfile>("/me/profile"), fetchMyFavorites(), fetchMyReviews()])
      .then(([loadedProfile, loadedFavorites, loadedReviews]) => {
        setProfile(loadedProfile);
        setFavorites(loadedFavorites.restaurants);
        setReviews(loadedReviews.reviews);
      })
      .catch((caught) => {
        if (
          (caught instanceof UserApiError || caught instanceof ReviewsApiError) &&
          caught.status === 401
        ) {
          router.replace("/login");
          return;
        }
        setError("目前無法載入個人頁面，請稍後再試。");
      });
  }, [router]);

  async function logout() {
    setLoggingOut(true);
    setLogoutError("");
    try {
      await userApi<void>("/auth/session", { method: "DELETE" });
      router.replace("/login");
      router.refresh();
    } catch {
      setLogoutError("登出失敗，請稍後再試。");
      setLoggingOut(false);
    }
  }

  if (error) return <ProfileState message={error} />;
  if (!profile) return <ProfileState message="正在整理你的 BiteMap 個人頁面…" loading />;

  return (
    <main className="profile-page" aria-labelledby="profile-title">
      <header className="profile-page__header">
        <h1 id="profile-title">個人頁面</h1>
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
          <section
            className="profile-merchant-application"
            aria-labelledby="merchant-application-title"
          >
            <div className="profile-merchant-application__heading">
              <IconBuildingStore aria-hidden="true" />
              <div>
                <h2 id="merchant-application-title">店家申請</h2>
                <p>想讓更多人找到你的店？申請功能即將開放。</p>
              </div>
            </div>
            <button type="button" className="button button--secondary" disabled>
              即將開放
            </button>
          </section>
        </aside>

        <section className="profile-content-card">
          <nav className="profile-tabs" aria-label="個人內容分類">
            <button
              type="button"
              className={tab === "food-map" ? "is-active" : undefined}
              onClick={() => setTab("food-map")}
              aria-current={tab === "food-map" ? "page" : undefined}
            >
              <IconMap2 aria-hidden="true" /> 美食地圖
            </button>
            <button
              type="button"
              className={tab === "reviews" ? "is-active" : undefined}
              onClick={() => setTab("reviews")}
              aria-current={tab === "reviews" ? "page" : undefined}
            >
              <IconMessageCircle aria-hidden="true" /> 美食留言
              <span>{reviews.length}</span>
            </button>
            <button
              type="button"
              className={tab === "favorites" ? "is-active" : undefined}
              onClick={() => setTab("favorites")}
              aria-current={tab === "favorites" ? "page" : undefined}
            >
              <IconBookmark aria-hidden="true" /> 收藏
              <span>{favorites.length}</span>
            </button>
          </nav>

          {tab === "food-map" ? <FoodMapPanel /> : null}

          {tab === "reviews" ? (
            <section className="profile-tab-panel" aria-labelledby="profile-reviews-title">
              <div className="profile-section-title">
                <IconMessageCircle aria-hidden="true" />
                <h2 id="profile-reviews-title">我的美食留言</h2>
                <span>{reviews.length} 筆</span>
              </div>
              {reviews.length > 0 ? (
                <div className="profile-reviews-list">
                  {reviews.map((review) => (
                    <ProfileReviewRow key={review.id} review={review} />
                  ))}
                </div>
              ) : (
                <div className="profile-tab-empty">
                  <IconMessageCircle aria-hidden="true" />
                  <h3>還沒有美食留言</h3>
                  <p>去餐廳頁寫下第一則留言，留下自己的再訪紀錄。</p>
                  <Link className="button button--secondary" href="/">
                    探索餐廳 <IconChevronRight aria-hidden="true" />
                  </Link>
                </div>
              )}
            </section>
          ) : null}

          {tab === "favorites" ? (
            <section className="profile-tab-panel" aria-labelledby="profile-favorites-title">
              <div className="profile-section-title">
                <IconBookmark aria-hidden="true" />
                <h2 id="profile-favorites-title">我的收藏</h2>
                <span>{favorites.length} 間</span>
              </div>
              {favorites.length > 0 ? (
                <div className="profile-favorites-list">
                  {favorites.map((restaurant) => (
                    <FavoriteRow key={restaurant.id} restaurant={restaurant} />
                  ))}
                </div>
              ) : (
                <div className="profile-tab-empty">
                  <IconBookmark aria-hidden="true" />
                  <h3>還沒有收藏餐廳</h3>
                  <p>在餐廳頁按下收藏，喜歡的店家就會集中在這裡。</p>
                  <Link className="button button--secondary" href="/">
                    找一家喜歡的店 <IconChevronRight aria-hidden="true" />
                  </Link>
                </div>
              )}
            </section>
          ) : null}
        </section>
      </section>

      <div className="profile-account-actions">
        <button
          className="button button--danger-quiet"
          type="button"
          onClick={logout}
          disabled={loggingOut}
        >
          <IconLogout aria-hidden="true" />
          {loggingOut ? "登出中…" : "登出"}
        </button>
        {logoutError ? (
          <p role="alert" className="profile-account-actions__error">
            {logoutError}
          </p>
        ) : null}
      </div>
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
