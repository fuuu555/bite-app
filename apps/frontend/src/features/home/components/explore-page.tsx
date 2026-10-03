"use client";

import {
  IconAdjustmentsHorizontal,
  IconArrowRight,
  IconRoute,
  IconSearch,
  IconToolsKitchen3,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import {
  ExploreApiError,
  FALLBACK_EXPLORE_LOCATION,
  type ExploreDistanceKm,
  type ExploreFilters,
  type ExploreLocation,
  type ExploreRestaurant,
  type ExploreRestaurantsResponse,
  type ExploreSort,
  explorePageSearchParams,
  exploreUrlState,
  fetchExploreRestaurants,
  formatExploreDistance,
} from "@/features/home/api/explore-api";
import {
  fetchPublicMapCuisines,
  type MapCuisine,
  priceRangeLabels,
} from "@/features/map/api/public-map-api";

const invalidQueryMessage = "店名請至少輸入 2 個字元，或直接使用條件探索。";

function parseDistance(value: string): ExploreDistanceKm | "" {
  if (value === "2" || value === "5" || value === "10") return Number(value) as ExploreDistanceKm;
  return "";
}

const sortOptions: Array<{ value: ExploreSort; label: string }> = [
  { value: "recommended", label: "推薦排序" },
  { value: "distance", label: "距離最近" },
  { value: "price", label: "價格由低到高" },
  { value: "revisit_rate", label: "App 再訪率" },
  { value: "google_rating", label: "Google 評分" },
  { value: "trust", label: "評論可信度" },
];

function RestaurantScores({ restaurant }: { restaurant: ExploreRestaurant }) {
  return (
    <div className="explore-restaurant-card__scores" aria-label="資料來源摘要">
      <span>
        <b>Google</b>
        {restaurant.google.rating === null ? "尚無資料" : restaurant.google.rating}
        {restaurant.google.review_count === null ? "" : `（${restaurant.google.review_count} 則）`}
      </span>
      <span>
        <b>BiteMap</b>
        {restaurant.app.revisit_rate === null ? "尚無資料" : `再訪 ${restaurant.app.revisit_rate}%`}
      </span>
    </div>
  );
}

function RestaurantVisualPlaceholder({ restaurant }: { restaurant: ExploreRestaurant }) {
  if (restaurant.photo_url) {
    return (
      <div className="explore-restaurant-visual has-photo">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={restaurant.photo_url} alt={`${restaurant.name}店家照片`} loading="lazy" />
      </div>
    );
  }

  return (
    <div
      className="explore-restaurant-visual"
      style={{ backgroundColor: restaurant.primary_cuisine.color }}
      aria-label="尚無餐廳照片"
    >
      <IconToolsKitchen3 aria-hidden="true" />
      <span>尚無照片</span>
    </div>
  );
}

function RestaurantFeatureCard({
  restaurant,
  rank,
}: {
  restaurant: ExploreRestaurant;
  rank: number;
}) {
  const distanceLabel = formatExploreDistance(restaurant.distance_meters);

  return (
    <article className="explore-feature-card">
      <div className="explore-feature-card__media">
        <RestaurantVisualPlaceholder restaurant={restaurant} />
        <span className="explore-feature-card__rank">Top {rank}</span>
      </div>
      <div className="explore-feature-card__body">
        <div className="explore-restaurant-card__cuisine">
          <IconToolsKitchen3 aria-hidden="true" />
          {restaurant.primary_cuisine.display_name}
        </div>
        <h3>{restaurant.name}</h3>
        <p>{restaurant.address}</p>
        <div className="explore-restaurant-card__meta">
          {distanceLabel ? <span>{distanceLabel}</span> : null}
          <span>{priceRangeLabels[restaurant.price_range]}</span>
        </div>
        <RestaurantScores restaurant={restaurant} />
        <Link className="explore-card-link" href={`/restaurants/${restaurant.id}`}>
          查看餐廳
          <IconArrowRight aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}

function RestaurantResultRow({ restaurant }: { restaurant: ExploreRestaurant }) {
  const distanceLabel = formatExploreDistance(restaurant.distance_meters);

  return (
    <article className="explore-result-row">
      <RestaurantVisualPlaceholder restaurant={restaurant} />
      <div className="explore-result-row__body">
        <div className="explore-restaurant-card__cuisine">
          <IconToolsKitchen3 aria-hidden="true" />
          {restaurant.primary_cuisine.display_name}
        </div>
        <h3>{restaurant.name}</h3>
        <p>{restaurant.address}</p>
        <div className="explore-restaurant-card__meta">
          {distanceLabel ? <span>{distanceLabel}</span> : null}
          <span>{priceRangeLabels[restaurant.price_range]}</span>
        </div>
        <RestaurantScores restaurant={restaurant} />
      </div>
      <Link className="explore-card-link" href={`/restaurants/${restaurant.id}`}>
        查看餐廳
        <IconArrowRight aria-hidden="true" />
      </Link>
    </article>
  );
}

function ExplorePageContent({
  initialQuery,
  initialFilters,
  initialSort,
}: {
  initialQuery: string;
  initialFilters: ExploreFilters;
  initialSort: ExploreSort;
}) {
  const router = useRouter();
  const query = initialQuery;
  const filters = initialFilters;
  const normalizedQuery = query.trim();
  const hasInvalidQuery = normalizedQuery.length === 1;
  const [draftQuery, setDraftQuery] = useState(query);
  const [draftFilters, setDraftFilters] = useState<ExploreFilters>(filters);
  const [cuisines, setCuisines] = useState<MapCuisine[]>([]);
  const [location, setLocation] = useState<ExploreLocation | null>(null);
  const [result, setResult] = useState<ExploreRestaurantsResponse | null>(null);
  const requiresLocation = Boolean(filters.distanceKm) || initialSort === "distance";
  const [isLoading, setIsLoading] = useState(!hasInvalidQuery);
  const [error, setError] = useState<string | null>(hasInvalidQuery ? invalidQueryMessage : null);
  const canSearchByDistance = !requiresLocation || location !== null;

  useEffect(() => {
    const controller = new AbortController();
    fetchPublicMapCuisines(controller.signal)
      .then(setCuisines)
      .catch(() => {
        if (!controller.signal.aborted) setCuisines([]);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!requiresLocation || location) return;

    if (!navigator.geolocation) {
      const timeoutId = window.setTimeout(() => {
        setLocation(FALLBACK_EXPLORE_LOCATION);
        setError("此瀏覽器不支援定位，已改用中原大學測試店位置計算距離。 ");
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocation({ latitude: coords.latitude, longitude: coords.longitude });
      },
      () => {
        setLocation(FALLBACK_EXPLORE_LOCATION);
        setError("無法取得目前位置，已改用中原大學測試店位置計算距離。 ");
      },
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 10_000 },
    );
  }, [location, requiresLocation]);

  useEffect(() => {
    if (hasInvalidQuery || !canSearchByDistance) return;

    const controller = new AbortController();
    fetchExploreRestaurants(
      normalizedQuery,
      filters,
      location ?? undefined,
      controller.signal,
      initialSort,
    )
      .then(setResult)
      .catch((requestError) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof ExploreApiError) {
          setError("目前無法載入探索結果，請稍後再試。");
        } else {
          setError("探索服務暫時無法使用。");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [canSearchByDistance, filters, hasInvalidQuery, initialSort, location, normalizedQuery]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = explorePageSearchParams(draftQuery, draftFilters, initialSort);
    router.push(params.size ? `/?${params.toString()}` : "/");
  }

  function changeSort(value: ExploreSort) {
    const params = explorePageSearchParams(query, filters, value);
    router.push(params.size ? `/?${params.toString()}` : "/");
  }

  return (
    <main className="explore-page">
      <header className="explore-page__header">
        <div className="explore-page__identity">
          <div className="explore-page__brandmark" aria-hidden="true">
            B
          </div>
          <div>
            <strong>BiteMap</strong>
            <span>探索附近餐廳</span>
          </div>
        </div>
        <div className="explore-page__intro">
          <h1>今天想吃什麼？</h1>
          <Link className="explore-travel-link" href="/travel">
            <IconRoute aria-hidden="true" />
            AI 規劃全台旅遊行程
            <IconArrowRight aria-hidden="true" />
          </Link>
        </div>
      </header>

      <form className="explore-search" onSubmit={search} aria-label="探索餐廳條件">
        <label className="explore-search__query">
          <span>餐廳名稱</span>
          <span className="explore-search__input">
            <IconSearch aria-hidden="true" />
            <input
              type="search"
              value={draftQuery}
              onChange={(event) => setDraftQuery(event.target.value)}
              placeholder="輸入餐廳名稱或地址"
            />
          </span>
        </label>
        <div className="explore-search__filters">
          <div className="explore-search__filters-title">
            <IconAdjustmentsHorizontal aria-hidden="true" />
            <span>篩選條件</span>
          </div>
          <label>
            <span>距離</span>
            <select
              value={draftFilters.distanceKm}
              onChange={(event) =>
                setDraftFilters((current) => ({
                  ...current,
                  distanceKm: parseDistance(event.target.value),
                }))
              }
            >
              <option value="">不限距離</option>
              <option value="2">2 km 內</option>
              <option value="5">5 km 內</option>
              <option value="10">10 km 內</option>
            </select>
          </label>
          <label>
            <span>價格</span>
            <select
              value={draftFilters.priceRange}
              onChange={(event) =>
                setDraftFilters((current) => ({
                  ...current,
                  priceRange: event.target.value as ExploreFilters["priceRange"],
                }))
              }
            >
              <option value="">不限價格</option>
              {Object.entries(priceRangeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>料理分類</span>
            <select
              value={draftFilters.cuisineId}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, cuisineId: event.target.value }))
              }
            >
              <option value="">不限料理</option>
              {cuisines.map((cuisine) => (
                <option key={cuisine.id} value={cuisine.id}>
                  {cuisine.display_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="button button--primary" type="submit" disabled={isLoading}>
          <IconSearch aria-hidden="true" />
          {isLoading ? "搜尋中…" : "開始探索"}
        </button>
      </form>

      {error ? <p className="explore-page__message is-error">{error}</p> : null}

      <section className="explore-section" aria-labelledby="top-three-title">
        <div className="explore-section__heading">
          <h2 id="top-three-title">
            <IconToolsKitchen3 aria-hidden="true" />
            本週 Top 3 必吃
          </h2>
        </div>
        {result?.top_restaurants.length ? (
          <div className="explore-top-three">
            {result.top_restaurants.map((restaurant, index) => (
              <RestaurantFeatureCard key={restaurant.id} restaurant={restaurant} rank={index + 1} />
            ))}
          </div>
        ) : (
          <div className="explore-empty">搜尋後會在這裡顯示前三筆結果。</div>
        )}
      </section>

      <section className="explore-section" aria-labelledby="all-results-title">
        <div className="explore-section__heading">
          <h2 id="all-results-title">
            <IconToolsKitchen3 aria-hidden="true" />
            完整搜尋結果
          </h2>
          <label className="explore-sort">
            <span>排序</span>
            <select value={initialSort} onChange={(event) => changeSort(event.target.value as ExploreSort)}>
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {result ? (
          result.restaurants.length ? (
            <div className="explore-results">
              {result.restaurants.map((restaurant) => (
                <RestaurantResultRow key={restaurant.id} restaurant={restaurant} />
              ))}
            </div>
          ) : (
            <div className="explore-empty">沒有符合目前條件的已發布店家。</div>
          )
        ) : (
          <div className="explore-empty">輸入店名或設定條件後開始探索。</div>
        )}
      </section>
    </main>
  );
}

function ExplorePageUrlState() {
  const searchParams = useSearchParams();
  const urlState = exploreUrlState(searchParams);
  return (
    <ExplorePageContent
      key={searchParams.toString()}
      initialQuery={urlState.query}
      initialFilters={urlState.filters}
      initialSort={urlState.sort}
    />
  );
}

function ExplorePageFallback() {
  return (
    <main className="explore-page">
      <header className="explore-page__header">
        <div>
          <h1>探索餐廳</h1>
        </div>
      </header>
      <section className="explore-section" aria-label="載入探索頁">
        <div className="explore-empty">正在載入探索條件…</div>
      </section>
    </main>
  );
}

export function ExplorePage() {
  return (
    <Suspense fallback={<ExplorePageFallback />}>
      <ExplorePageUrlState />
    </Suspense>
  );
}
