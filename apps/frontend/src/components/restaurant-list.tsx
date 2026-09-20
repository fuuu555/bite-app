"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { Restaurant, adminApi, priceRangeLabels } from "@/lib/admin-api";

const statusLabels = { draft: "草稿", published: "已發布", archived: "已封存" };
const RESTAURANTS_PER_PAGE = 8;

export function RestaurantList() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [regionFilter, setRegionFilter] = useState("");
  const [cuisineFilter, setCuisineFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  async function refresh() {
    const data = await adminApi<Restaurant[]>("/restaurants");
    setRestaurants(data);
  }

  useEffect(() => {
    let active = true;
    adminApi<Restaurant[]>("/restaurants")
      .then((data) => {
        if (active) setRestaurants(data);
      })
      .catch(() => {
        if (active) setError("無法載入店家，請確認 API 與資料庫狀態。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function restore(restaurant: Restaurant) {
    try {
      await adminApi<Restaurant>(`/restaurants/${restaurant.id}/restore`, { method: "POST" });
      await refresh();
    } catch {
      setError("無法解封店家，請稍後再試。 ");
    }
  }

  async function remove(restaurant: Restaurant) {
    if (!window.confirm(`確定要刪除「${restaurant.name}」嗎？此操作無法復原。`)) return;
    try {
      await adminApi<void>(`/restaurants/${restaurant.id}`, { method: "DELETE" });
      await refresh();
    } catch {
      setError("無法刪除店家，請稍後再試。 ");
    }
  }

  const cuisines = Array.from(
    new Map(
      restaurants
        .filter((restaurant) => restaurant.primary_cuisine)
        .map((restaurant) => [restaurant.primary_cuisine!.id, restaurant.primary_cuisine!]),
    ).values(),
  );
  const normalizedRegion = regionFilter.trim().toLowerCase();
  const filteredRestaurants = restaurants.filter((restaurant) => {
    const matchesRegion =
      !normalizedRegion || restaurant.address.toLowerCase().includes(normalizedRegion);
    const matchesCuisine = !cuisineFilter || restaurant.primary_cuisine_id === cuisineFilter;
    const matchesStatus = !statusFilter || restaurant.status === statusFilter;
    return matchesRegion && matchesCuisine && matchesStatus;
  });
  const pageCount = Math.max(1, Math.ceil(filteredRestaurants.length / RESTAURANTS_PER_PAGE));
  const safeCurrentPage = Math.min(currentPage, pageCount);
  const visibleRestaurants = filteredRestaurants.slice(
    (safeCurrentPage - 1) * RESTAURANTS_PER_PAGE,
    safeCurrentPage * RESTAURANTS_PER_PAGE,
  );

  return (
    <main className="admin-page">
      <header className="admin-page__header">
        <div>
          <h1>店家管理</h1>
          <p>建立、定位並確認店家資料後再發布到公開地圖。</p>
        </div>
        <Link href="/admin/restaurants/new" className="button button--primary">
          <Icon name="plus" />
          新增店家
        </Link>
      </header>

      {error ? <p className="form-message is-error">{error}</p> : null}
      {loading ? (
        <div className="table-skeleton" aria-label="載入店家" aria-busy="true" />
      ) : restaurants.length === 0 ? (
        <section className="empty-state">
          <Icon name="map" />
          <h2>還沒有店家資料</h2>
          <p>先建立第一間店家，設定座標、主要料理與價格後即可發布。</p>
          <Link href="/admin/restaurants/new" className="button button--primary">
            新增第一間店家
          </Link>
        </section>
      ) : (
        <>
          <section className="restaurant-filters" aria-label="店家篩選">
            <label>
              地區／地址
              <input
                type="search"
                placeholder="例如：台北市、中山區"
                value={regionFilter}
                onChange={(event) => {
                  setRegionFilter(event.target.value);
                  setCurrentPage(1);
                }}
              />
            </label>
            <label>
              餐廳類別
              <select
                value={cuisineFilter}
                onChange={(event) => {
                  setCuisineFilter(event.target.value);
                  setCurrentPage(1);
                }}
              >
                <option value="">全部料理</option>
                {cuisines.map((cuisine) => (
                  <option key={cuisine.id} value={cuisine.id}>
                    {cuisine.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              狀態
              <select
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value);
                  setCurrentPage(1);
                }}
              >
                <option value="">全部狀態</option>
                <option value="draft">草稿</option>
                <option value="published">已發布</option>
                <option value="archived">已封存</option>
              </select>
            </label>
          </section>
          {filteredRestaurants.length === 0 ? (
            <section className="empty-state">
              <Icon name="map" />
              <h2>沒有符合條件的店家</h2>
              <p>請調整地區、料理分類或狀態篩選。</p>
            </section>
          ) : (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>店家</th>
                    <th>主要料理</th>
                    <th>價格</th>
                    <th>狀態</th>
                    <th>
                      <span className="sr-only">操作</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRestaurants.map((restaurant) => (
                    <tr key={restaurant.id}>
                      <td>
                        <strong>{restaurant.name}</strong>
                        <small>{restaurant.address}</small>
                        {restaurant.menu_url ? (
                          <a href={restaurant.menu_url} target="_blank" rel="noreferrer">
                            查看菜單
                          </a>
                        ) : null}
                      </td>
                      <td>{restaurant.primary_cuisine?.display_name ?? "尚未設定"}</td>
                      <td>
                        {restaurant.price_range
                          ? priceRangeLabels[restaurant.price_range]
                          : "尚未設定"}
                      </td>
                      <td>
                        <span className={`status-badge is-${restaurant.status}`}>
                          {statusLabels[restaurant.status]}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <Link href={`/admin/restaurants/${restaurant.id}`} className="text-link">
                            編輯
                          </Link>
                          {restaurant.status === "archived" ? (
                            <button
                              type="button"
                              className="button button--quiet"
                              onClick={() => restore(restaurant)}
                            >
                              解封
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="button button--danger-quiet"
                            onClick={() => remove(restaurant)}
                          >
                            刪除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {filteredRestaurants.length > RESTAURANTS_PER_PAGE ? (
            <nav className="admin-pagination" aria-label="店家分頁">
              <button
                type="button"
                className="button button--quiet"
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                disabled={safeCurrentPage === 1}
              >
                上一頁
              </button>
              <span>
                第 {safeCurrentPage} / {pageCount} 頁
              </span>
              <button
                type="button"
                className="button button--quiet"
                onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))}
                disabled={safeCurrentPage === pageCount}
              >
                下一頁
              </button>
            </nav>
          ) : null}
        </>
      )}
    </main>
  );
}
