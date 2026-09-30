"use client";

import {
  IconArrowLeft,
  IconBook2,
  IconBookmark,
  IconChartBar,
  IconClock,
  IconChevronLeft,
  IconChevronRight,
  IconExternalLink,
  IconMap2,
  IconMapPin,
  IconPhoto,
  IconShare3,
  IconShieldCheck,
  IconStar,
  IconToolsKitchen3,
  IconUserPlus,
} from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  ExploreApiError,
  distanceBetweenLocations,
  formatExploreDistance,
  type ExploreLocation,
  type ExplorePhoto,
  type ExploreRestaurantDetail,
  fetchExploreRestaurant,
} from "@/lib/explore-api";
import { priceRangeLabels } from "@/lib/public-map-api";
import { fetchFavoriteState, setFavorite } from "@/lib/reviews-api";
import { RestaurantReviewsPanel } from "@/components/user/restaurant-reviews-panel";

function RestaurantPhotoLink({
  photo,
  className,
  priority = false,
}: {
  photo: ExplorePhoto;
  className?: string;
  priority?: boolean;
}) {
  return (
    <a
      className={className}
      href={photo.url}
      target="_blank"
      rel="noreferrer"
      aria-label={photo.alt_text || "開啟餐廳照片"}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photo.url}
        alt={photo.alt_text || "餐廳照片"}
        loading={priority ? "eager" : "lazy"}
      />
    </a>
  );
}

function RestaurantPhotoCarousel({
  photos,
  restaurantName,
}: {
  photos: ExplorePhoto[];
  restaurantName: string;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const trackRef = useRef<HTMLUListElement>(null);

  const moveToPhoto = (index: number) => {
    // Modulo keeps previous/next controls circular without duplicating carousel slides.
    // 透過餘數讓上一張／下一張循環切換，不需要複製首尾投影片。
    const nextIndex = (index + photos.length) % photos.length;
    const track = trackRef.current;
    const slide = track?.children[nextIndex] as HTMLElement | undefined;

    if (track && slide) {
      track.scrollTo({ left: slide.offsetLeft, behavior: "smooth" });
    }
    setActiveIndex(nextIndex);
  };

  if (photos.length === 0) {
    return (
      <section className="restaurant-detail-v3__photo-empty" aria-label="照片空狀態">
        <IconPhoto aria-hidden="true" />
        <strong>尚未建立照片資料</strong>
        <span>店家照片會在資料建立後顯示</span>
      </section>
    );
  }

  return (
    <div
      className="restaurant-detail-v3__carousel"
      role="region"
      aria-roledescription="carousel"
      aria-label={`${restaurantName}照片`}
    >
      <ul
        ref={trackRef}
        className="restaurant-detail-v3__carousel-track"
        onScroll={(event) => {
          const track = event.currentTarget;
          const slide = track.children[0] as HTMLElement | undefined;
          if (!slide) return;
          setActiveIndex(
            Math.min(
              photos.length - 1,
              Math.max(0, Math.round(track.scrollLeft / slide.offsetWidth)),
            ),
          );
        }}
      >
        {photos.map((photo, index) => (
          <li
            key={photo.id}
            className="restaurant-detail-v3__carousel-slide"
            aria-label={`第 ${index + 1} 張，共 ${photos.length} 張`}
          >
            <RestaurantPhotoLink
              photo={photo}
              className="restaurant-detail-v3__hero-link"
              priority={index === 0}
            />
          </li>
        ))}
      </ul>

      {photos.length > 1 ? (
        <>
          <button
            type="button"
            className="restaurant-detail-v3__carousel-control is-prev"
            onClick={() => moveToPhoto(activeIndex - 1)}
            aria-label="上一張照片"
          >
            <IconChevronLeft aria-hidden="true" />
          </button>
          <button
            type="button"
            className="restaurant-detail-v3__carousel-control is-next"
            onClick={() => moveToPhoto(activeIndex + 1)}
            aria-label="下一張照片"
          >
            <IconChevronRight aria-hidden="true" />
          </button>
          <nav className="restaurant-detail-v3__carousel-dots" aria-label="照片選擇">
            {photos.map((photo, index) => (
              <button
                key={photo.id}
                type="button"
                className={index === activeIndex ? "is-active" : undefined}
                onClick={() => moveToPhoto(index)}
                aria-label={`查看第 ${index + 1} 張照片`}
                aria-current={index === activeIndex ? "true" : undefined}
              />
            ))}
          </nav>
        </>
      ) : null}

      <p className="restaurant-detail-v3__carousel-count">
        {activeIndex + 1} / {photos.length}
      </p>
    </div>
  );
}

export function RestaurantDetailPage({ restaurantId }: { restaurantId: string }) {
  const [location, setLocation] = useState<ExploreLocation | null>(null);
  const [contentVersion, setContentVersion] = useState(0);
  const [favorited, setFavorited] = useState(false);
  const [favoriteBusy, setFavoriteBusy] = useState(false);
  const [loadResult, setLoadResult] = useState<{
    restaurantId: string;
    restaurant: ExploreRestaurantDetail | null;
    state: "loading" | "ready" | "missing" | "error";
  }>({ restaurantId, restaurant: null, state: "loading" });

  useEffect(() => {
    // Location is optional enrichment; denying permission must not block restaurant details.
    // 定位只用來補充距離，使用者拒絕權限時仍須正常顯示餐廳資料。
    if (!navigator.geolocation) return;
    let active = true;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (active) setLocation({ latitude: coords.latitude, longitude: coords.longitude });
      },
      () => undefined,
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 10_000 },
    );
    return () => {
      active = false;
    };
  }, [restaurantId]);

  useEffect(() => {
    // Abort the previous detail request when the dynamic route changes.
    // 動態路由切換時取消上一筆詳情請求，避免舊回應覆蓋新店家。
    const controller = new AbortController();
    fetchExploreRestaurant(restaurantId, controller.signal)
      .then((result) => {
        setLoadResult({ restaurantId, restaurant: result, state: "ready" });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadResult({
          restaurantId,
          restaurant: null,
          state: error instanceof ExploreApiError && error.status === 404 ? "missing" : "error",
        });
      });
    return () => controller.abort();
  }, [restaurantId, contentVersion]);

  useEffect(() => {
    let active = true;
    fetchFavoriteState(restaurantId)
      .then((result) => {
        if (active) setFavorited(result.favorited);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [restaurantId]);

  // Keep stale data hidden during a route transition, even before the effect starts its next request.
  // 路由切換到新店家時立即隱藏舊資料，不等待下一個 effect 開始請求。
  const isCurrentRestaurant = loadResult.restaurantId === restaurantId;
  const state = isCurrentRestaurant ? loadResult.state : "loading";
  const restaurant = isCurrentRestaurant ? loadResult.restaurant : null;

  if (state === "loading") {
    return <main className="restaurant-detail-state">正在載入餐廳資料…</main>;
  }

  if (state !== "ready" || !restaurant) {
    return (
      <main className="restaurant-detail-state">
        <h1>{state === "missing" ? "找不到已發布店家" : "餐廳資料暫時無法載入"}</h1>
        <p>可以返回探索頁重新搜尋，或從地圖查看其他店家。</p>
        <nav aria-label="錯誤恢復操作">
          <Link className="button button--secondary" href="/">
            返回探索
          </Link>
          <Link className="button button--primary" href="/map">
            開啟地圖
          </Link>
        </nav>
      </main>
    );
  }

  const distanceMeters =
    location && restaurant.latitude !== null && restaurant.longitude !== null
      ? distanceBetweenLocations(location, {
          latitude: restaurant.latitude,
          longitude: restaurant.longitude,
        })
      : restaurant.distance_meters;
  const hasVisitIntentData = restaurant.app.revisit_rate !== null;
  const priceLabel = priceRangeLabels[restaurant.price_range];
  const menuLink = restaurant.menu.url ?? restaurant.menus[0]?.url ?? null;
  const coverPhoto =
    restaurant.photos.find((photo) => photo.url === restaurant.photo_url) ??
    (restaurant.photo_url
      ? { id: `cover-${restaurant.id}`, url: restaurant.photo_url, alt_text: null }
      : null);
  const detailPhotos = coverPhoto
    ? [coverPhoto, ...restaurant.photos.filter((photo) => photo.url !== coverPhoto.url)]
    : restaurant.photos;

  const toggleFavorite = async () => {
    const nextFavorited = !favorited;
    setFavorited(nextFavorited);
    setFavoriteBusy(true);
    try {
      await setFavorite(restaurantId, nextFavorited);
    } catch {
      setFavorited(!nextFavorited);
    } finally {
      setFavoriteBusy(false);
    }
  };

  return (
    <main className="restaurant-detail-page restaurant-detail-v3">
      <nav className="restaurant-detail-v3__nav" aria-label="詳細頁導覽">
        <Link href="/">
          <IconArrowLeft aria-hidden="true" />
          返回探索
        </Link>
        <Link href="/map">
          <IconMap2 aria-hidden="true" />
          回到地圖
        </Link>
      </nav>

      <article className="restaurant-detail-v3__overview">
        <figure className="restaurant-detail-v3__hero">
          <RestaurantPhotoCarousel photos={detailPhotos} restaurantName={restaurant.name} />
        </figure>

        <section className="restaurant-detail-v3__identity" aria-labelledby="restaurant-title">
          <header>
            <p className="restaurant-detail-v3__cuisine">
              <IconToolsKitchen3 aria-hidden="true" />
              {restaurant.primary_cuisine.display_name}
            </p>
            <p className="restaurant-detail-v3__verified">
              <IconShieldCheck aria-hidden="true" />
              店家資訊待驗證
            </p>
            <h1 id="restaurant-title">{restaurant.name}</h1>
            <address>
              <IconMapPin aria-hidden="true" />
              {restaurant.address}
            </address>
            <p className="restaurant-detail-v3__hours">
              <IconClock aria-hidden="true" />
              營業資訊尚未提供
            </p>
          </header>

          <section className="restaurant-detail-v3__quick" aria-labelledby="quick-info-title">
            <h2 id="quick-info-title">快速資訊</h2>
            <dl>
              <div>
                <dt>距離</dt>
                <dd>{formatExploreDistance(distanceMeters)}</dd>
              </div>
              <div>
                <dt>價格</dt>
                <dd>{priceLabel}</dd>
              </div>
              <div>
                <dt>料理</dt>
                <dd>{restaurant.primary_cuisine.display_name}</dd>
              </div>
              <div>
                <dt>菜單</dt>
                <dd>{menuLink ? "已提供" : "尚未提供"}</dd>
              </div>
            </dl>
          </section>

          <nav className="restaurant-detail-v3__actions" aria-label="餐廳操作">
            <button
              type="button"
              className={favorited ? "is-primary is-active" : undefined}
              onClick={() => void toggleFavorite()}
              disabled={favoriteBusy}
              aria-pressed={favorited}
              aria-label={favorited ? "取消收藏" : "收藏"}
            >
              <IconBookmark aria-hidden="true" />
              {favorited ? "已收藏" : "收藏店家"}
            </button>
            {menuLink ? (
              <a
                className="restaurant-detail-v3__menu-action"
                href={menuLink}
                target="_blank"
                rel="noreferrer"
              >
                <IconBook2 aria-hidden="true" />
                餐廳菜單
                <IconExternalLink aria-hidden="true" />
              </a>
            ) : (
              <button type="button" disabled className="restaurant-detail-v3__menu-action">
                <IconBook2 aria-hidden="true" />
                餐廳菜單
              </button>
            )}
            <button type="button" disabled className="is-primary">
              <IconUserPlus aria-hidden="true" />
              發起約飯
            </button>
            <button type="button" disabled>
              <IconShare3 aria-hidden="true" />
              轉貼朋友
            </button>
          </nav>
          <p id="future-actions-note" className="restaurant-detail-v3__future-note">
            約飯與分享將在後續階段開放
          </p>
        </section>
      </article>

      <section className="restaurant-detail-v3__content" aria-label="餐廳完整資訊">
        <article className="restaurant-detail-v3__intent" aria-labelledby="intent-title">
          <header>
            <h2 id="intent-title">BiteMap 實訪意願指數</h2>
            <p>
              {restaurant.app.rating_count !== null
                ? `計 ${restaurant.app.rating_count} 人實訪紀錄`
                : "來自 BiteMap 使用者的實訪資料"}
            </p>
          </header>
          {hasVisitIntentData ? (
            <figure className="restaurant-detail-v3__distribution">
              <p>
                <strong>{restaurant.app.revisit_rate}%</strong>
                <span>願意再訪</span>
              </p>
              <meter
                min={0}
                max={100}
                value={restaurant.app.revisit_rate ?? 0}
                aria-label={`願意再訪 ${restaurant.app.revisit_rate}%`}
              />
              <figcaption>
                {restaurant.app.will_return_count ?? 0} 會再訪 · {restaurant.app.neutral_count ?? 0}{" "}
                普通 · {restaurant.app.will_not_return_count ?? 0} 不會
              </figcaption>
            </figure>
          ) : (
            <section className="restaurant-detail-v3__empty" aria-label="BiteMap 評價空狀態">
              <IconChartBar aria-hidden="true" />
              <strong>目前尚無足夠 BiteMap 評價資料</strong>
              <span>成為第一位留下實訪紀錄的使用者</span>
            </section>
          )}
        </article>

        <aside className="restaurant-detail-v3__google" aria-labelledby="google-title">
          <header>
            <IconStar aria-hidden="true" />
            <h2 id="google-title">Google 資料</h2>
          </header>
          <dl>
            <div>
              <dt>Google 評分</dt>
              <dd>{restaurant.google.rating ?? "尚未接入"}</dd>
            </div>
            <div>
              <dt>評論數</dt>
              <dd>{restaurant.google.review_count ?? "尚未接入"}</dd>
            </div>
          </dl>
          <p>外部評分與 BiteMap 實訪意願分開呈現。</p>
        </aside>
      </section>

      <RestaurantReviewsPanel
        restaurantId={restaurantId}
        onReviewsChanged={() => setContentVersion((version) => version + 1)}
      />
    </main>
  );
}
