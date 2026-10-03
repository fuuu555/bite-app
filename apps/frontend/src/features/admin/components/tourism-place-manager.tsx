"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  adminApi,
  type TourismAdminPlace,
  type TourismAdminPlacesResponse,
  type TourismDuplicatePairsResponse,
  type TourismImportRun,
  type TourismPlaceDeleteResponse,
  type TourismPlacesDeleteResponse,
} from "@/features/admin/api/admin-api";
import { TourismIcon } from "@/features/admin/components/cuisine-icon-picker";
import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";
import {
  citySuggestions,
  taiwanAdministrativeAreas,
} from "@/features/map/components/map-search-controls";

const PAGE_SIZE = 50;
const datasetLabels: Record<TourismImportRun["source_dataset"], string> = {
  food: "餐飲",
  attraction: "景點",
  hotel: "旅館民宿",
  service_site: "旅遊服務站",
};

type EditingPlace = {
  id: string;
  name: string;
  address: string;
};

type TourismView = "places" | "duplicates";

function regionLabel(address: string | null): string {
  if (!address) return "未提供地區";
  const match = address.match(/^(.{2,4}[縣市])\s*(.{1,4}[區鄉鎮市])/);
  return match ? `${match[1]} ${match[2]}` : address.slice(0, 8);
}

export function TourismPlaceManager({ refreshVersion }: { refreshVersion: number }) {
  const router = useRouter();
  const [dataset, setDataset] = useState("");
  const [filterCity, setFilterCity] = useState("");
  const [filterDistrict, setFilterDistrict] = useState("");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [view, setView] = useState<TourismView>("places");
  const [page, setPage] = useState(0);
  const [response, setResponse] = useState<TourismAdminPlacesResponse | null>(null);
  const [duplicateResponse, setDuplicateResponse] = useState<TourismDuplicatePairsResponse | null>(
    null,
  );
  const [editing, setEditing] = useState<EditingPlace | null>(null);
  const [placeToDelete, setPlaceToDelete] = useState<TourismAdminPlace | null>(null);
  const [selectedPlaces, setSelectedPlaces] = useState<TourismAdminPlace[]>([]);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const loadPlaces = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        offset: String(page * PAGE_SIZE),
        limit: String(PAGE_SIZE),
      });
      if (dataset) params.set("dataset", dataset);
      if (submittedQuery) params.set("query", submittedQuery);
      if (filterCity) params.set("city", filterCity);
      if (filterDistrict) params.set("district", filterDistrict);
      if (view === "duplicates") {
        setResponse(null);
        setDuplicateResponse(
          await adminApi<TourismDuplicatePairsResponse>(`/tourism/places/duplicates?${params}`),
        );
      } else {
        setDuplicateResponse(null);
        setResponse(await adminApi<TourismAdminPlacesResponse>(`/tourism/places?${params}`));
      }
    } catch {
      setMessage("無法載入觀光署資料店家。");
    } finally {
      setLoading(false);
    }
  }, [dataset, filterCity, filterDistrict, page, submittedQuery, view]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPlaces(), 0);
    return () => window.clearTimeout(timer);
  }, [loadPlaces, refreshVersion]);

  const groupedPlaces = useMemo(() => {
    const groups = new Map<string, TourismAdminPlace[]>();
    for (const place of response?.places ?? []) {
      const region = regionLabel(place.address);
      groups.set(region, [...(groups.get(region) ?? []), place]);
    }
    return [...groups.entries()];
  }, [response]);
  const totalCount =
    view === "duplicates" ? (duplicateResponse?.total ?? 0) : (response?.total ?? 0);
  const hasMore =
    view === "duplicates" ? (duplicateResponse?.has_more ?? false) : (response?.has_more ?? false);

  async function enableAll() {
    setBusy(true);
    try {
      const params = dataset ? `?dataset=${encodeURIComponent(dataset)}` : "";
      const result = await adminApi<{ enabled_count: number }>(
        `/tourism/places/enable-all${params}`,
        {
          method: "POST",
        },
      );
      setMessage(`已加入 ${result.enabled_count} 筆觀光署資料到地圖。`);
      await loadPlaces();
    } catch {
      setMessage("批次加入觀光署資料失敗。");
    } finally {
      setBusy(false);
    }
  }

  async function deletePlace(place: TourismAdminPlace) {
    setBusy(true);
    try {
      await adminApi<TourismPlaceDeleteResponse>(`/tourism/places/${place.id}`, {
        method: "DELETE",
      });
      setPlaceToDelete(null);
      setSelectedPlaces([]);
      setMessage(`已刪除觀光署來源資料「${place.name}」；重新匯入不會使它復活。`);
      await loadPlaces();
    } catch {
      setMessage("刪除觀光署來源資料失敗。請稍後再試。");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelectedPlaces() {
    if (!selectedPlaces.length) return;
    setBusy(true);
    try {
      const result = await adminApi<TourismPlacesDeleteResponse>("/tourism/places/delete-batch", {
        method: "POST",
        body: JSON.stringify({ place_ids: selectedPlaces.map((place) => place.id) }),
      });
      setConfirmBulkDelete(false);
      setSelectedPlaces([]);
      setMessage(
        `已永久刪除 ${result.deleted_count} 筆觀光署來源資料；重新匯入不會使它們復原。已連結的 BiteMap 店家會保留。`,
      );
      await loadPlaces();
    } catch {
      setMessage("批次刪除失敗；本次資料未刪除，請重新整理後再試。");
    } finally {
      setBusy(false);
    }
  }

  function togglePlaceSelection(place: TourismAdminPlace) {
    setSelectedPlaces((current) => {
      if (current.some((selected) => selected.id === place.id)) {
        return current.filter((selected) => selected.id !== place.id);
      }
      if (current.length >= 100) {
        setMessage("一次最多可批次刪除 100 筆，請分批處理。");
        return current;
      }
      return [...current, place];
    });
  }

  function changeView(nextView: TourismView) {
    setSelectedPlaces([]);
    setView(nextView);
    setPage(0);
    setEditing(null);
  }

  function startEditing(place: TourismAdminPlace) {
    setEditing({
      id: place.id,
      name: place.name,
      address: place.address ?? "",
    });
    setMessage("");
  }

  async function saveEditing() {
    if (!editing) return;
    setBusy(true);
    try {
      await adminApi(`/tourism/places/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editing.name,
          address: editing.address.trim() || null,
        }),
      });
      setEditing(null);
      setMessage("觀光署資料店家已更新。");
      await loadPlaces();
    } catch {
      setMessage("更新觀光署資料店家失敗。");
    } finally {
      setBusy(false);
    }
  }

  async function convert(place: TourismAdminPlace) {
    setBusy(true);
    try {
      const restaurant = await adminApi<{ id: string }>(`/tourism/places/${place.id}/convert`, {
        method: "POST",
        body: JSON.stringify({ google_lookup_enabled: false }),
      });
      router.push(`/admin/restaurants/${restaurant.id}`);
    } catch {
      setMessage("轉換失敗，可能已有相同名稱與地址的 BiteMap 店家。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tourism-place-manager" aria-labelledby="tourism-place-manager-title">
      <div className="tourism-place-manager__header">
        <div>
          <h2 id="tourism-place-manager-title">觀光署資料店家</h2>
          <p>
            可編輯官方名稱與地址；分類圖示依觀光資料類型自動套用。餐飲資料可再轉成 BiteMap 店家。
          </p>
        </div>
        {view === "places" ? (
          <button
            type="button"
            className="button button--primary"
            onClick={() => void enableAll()}
            disabled={busy}
          >
            全部加入地圖
          </button>
        ) : null}
      </div>

      <div className="tourism-place-manager__views" role="group" aria-label="觀光資料檢視方式">
        <button
          type="button"
          className={`button ${view === "places" ? "button--primary" : "button--quiet"}`}
          aria-pressed={view === "places"}
          onClick={() => changeView("places")}
        >
          全部資料
        </button>
        <button
          type="button"
          className={`button ${view === "duplicates" ? "button--primary" : "button--quiet"}`}
          aria-pressed={view === "duplicates"}
          onClick={() => changeView("duplicates")}
        >
          疑似重複
        </button>
      </div>

      <div
        className={`tourism-place-manager__filters${view === "duplicates" ? " is-duplicate" : ""}`}
      >
        <label>
          資料類型
          <select
            value={dataset}
            onChange={(event) => {
              setSelectedPlaces([]);
              setDataset(event.target.value);
              setPage(0);
            }}
          >
            <option value="">全部資料</option>
            {Object.entries(datasetLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          縣市
          <select
            value={filterCity}
            onChange={(event) => {
              setSelectedPlaces([]);
              setFilterCity(event.target.value);
              setFilterDistrict("");
              setPage(0);
            }}
          >
            <option value="">全部縣市</option>
            {citySuggestions.map((city) => (
              <option key={city} value={city}>
                {city}
              </option>
            ))}
          </select>
        </label>
        <label>
          行政區
          <select
            value={filterDistrict}
            onChange={(event) => {
              setSelectedPlaces([]);
              setFilterDistrict(event.target.value);
              setPage(0);
            }}
            disabled={!filterCity}
          >
            <option value="">全部行政區</option>
            {(taiwanAdministrativeAreas[filterCity] ?? []).map((district) => (
              <option key={district} value={district}>
                {district}
              </option>
            ))}
          </select>
        </label>
        <label>
          名稱／地址關鍵字
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setSelectedPlaces([]);
                setPage(0);
                setSubmittedQuery(query.trim());
              }
            }}
            placeholder="搜尋官方資料"
          />
        </label>
        <button
          type="button"
          className="button button--quiet"
          onClick={() => {
            setSelectedPlaces([]);
            setPage(0);
            setSubmittedQuery(query.trim());
          }}
          disabled={loading}
        >
          搜尋
        </button>
      </div>

      {message ? <p className="form-message">{message}</p> : null}
      {loading ? <div className="table-skeleton" aria-busy="true" /> : null}
      {!loading && view === "duplicates" && !duplicateResponse?.pairs.length ? (
        <p className="empty-state">目前沒有找到疑似重複的觀光署資料。</p>
      ) : null}
      {!loading && view !== "duplicates" && !response?.places.length ? (
        <p className="empty-state">目前沒有觀光署資料，請先執行上方匯入。</p>
      ) : null}

      {!loading && view === "duplicates" && duplicateResponse?.pairs.length ? (
        <>
          {selectedPlaces.length ? (
            <div
              className="tourism-place-manager__bulk-actions"
              role="region"
              aria-label="批次刪除選取項目"
            >
              <strong>已選取 {selectedPlaces.length} 筆</strong>
              <button
                type="button"
                className="button button--quiet"
                onClick={() => setSelectedPlaces([])}
                disabled={busy}
              >
                清除選取
              </button>
              <button
                type="button"
                className="button button--danger"
                onClick={() => setConfirmBulkDelete(true)}
                disabled={busy}
              >
                批次永久刪除
              </button>
            </div>
          ) : null}
          <div className="tourism-place-manager__duplicates">
            {duplicateResponse.pairs.map((pair) => (
              <section
                className="tourism-place-manager__duplicate"
                key={`${pair.left.id}:${pair.right.id}`}
              >
                <header>
                  <strong>疑似重複</strong>
                  <span>
                    {pair.match_reasons.join(" · ")} · 名稱相似度{" "}
                    {Math.round(pair.name_similarity * 100)}%
                  </span>
                </header>
                <div className="tourism-place-manager__duplicate-pair">
                  {[pair.left, pair.right].map((place) => (
                    <article key={place.id}>
                      <label className="tourism-place-manager__duplicate-select">
                        <input
                          type="checkbox"
                          checked={selectedPlaces.some((selected) => selected.id === place.id)}
                          onChange={() => togglePlaceSelection(place)}
                          disabled={
                            busy ||
                            (selectedPlaces.length >= 100 &&
                              !selectedPlaces.some((selected) => selected.id === place.id))
                          }
                          aria-label={`選取刪除 ${place.name}`}
                        />
                        選取
                      </label>
                      <small>
                        {datasetLabels[place.source_dataset]} · {place.source_record_id}
                      </small>
                      <strong>{place.name}</strong>
                      <span>{place.address ?? "尚無地址"}</span>
                      {place.linked_restaurant_id ? (
                        <small>已連結 BiteMap 店家；刪除來源資料不會刪除該店家</small>
                      ) : null}
                      <button
                        type="button"
                        className="button button--quiet button--danger"
                        onClick={() => setPlaceToDelete(place)}
                        disabled={busy}
                      >
                        刪除此筆
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </>
      ) : null}

      {!loading
        ? groupedPlaces.map(([region, places]) => (
            <section
              key={region}
              className="tourism-place-manager__region"
              aria-labelledby={`tourism-region-${region}`}
            >
              <h3 id={`tourism-region-${region}`}>
                {region} <span>{places.length} 筆</span>
              </h3>
              <div className="tourism-place-manager__list">
                {places.map((place) =>
                  editing?.id === place.id ? (
                    <div className="tourism-place-manager__item is-editing" key={place.id}>
                      <input
                        value={editing.name}
                        onChange={(event) => setEditing({ ...editing, name: event.target.value })}
                        aria-label="店家名稱"
                      />
                      <input
                        value={editing.address}
                        onChange={(event) =>
                          setEditing({ ...editing, address: event.target.value })
                        }
                        aria-label="完整地址"
                        placeholder="縣市、行政區、街道與門牌"
                      />
                      <span className="tourism-place-manager__classification">
                        {datasetLabels[place.source_dataset]}（系統自動分類）
                      </span>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button button--primary"
                          onClick={() => void saveEditing()}
                          disabled={busy}
                        >
                          儲存
                        </button>
                        <button
                          type="button"
                          className="button button--quiet"
                          onClick={() => setEditing(null)}
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    <article className="tourism-place-manager__item" key={place.id}>
                      {place.icon_key ? (
                        <span
                          className="tourism-place-manager__icon icon-color-marker"
                          style={{ backgroundColor: place.icon_color }}
                          aria-label="資料圖示"
                        >
                          <TourismIcon iconKey={place.icon_key} size={25} />
                        </span>
                      ) : (
                        <span
                          className="tourism-place-manager__icon is-unassigned"
                          aria-label="尚未建立圖示分類"
                        >
                          —
                        </span>
                      )}
                      <div>
                        <strong>{place.name}</strong>
                        <small>
                          {place.address ?? "尚無地址"} · {datasetLabels[place.source_dataset]}
                        </small>
                      </div>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button button--quiet"
                          onClick={() => startEditing(place)}
                        >
                          編輯
                        </button>
                        {place.category === "restaurant" ? (
                          place.linked_restaurant_id ? (
                            <Link
                              className="text-link"
                              href={`/admin/restaurants/${place.linked_restaurant_id}`}
                            >
                              查看 BiteMap 店家
                            </Link>
                          ) : (
                            <button
                              type="button"
                              className="button button--quiet"
                              onClick={() => void convert(place)}
                              disabled={busy}
                            >
                              轉成 BiteMap 店家
                            </button>
                          )
                        ) : null}
                      </div>
                    </article>
                  ),
                )}
              </div>
            </section>
          ))
        : null}

      {totalCount ? (
        <nav className="admin-pagination" aria-label="觀光署資料分頁">
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              setSelectedPlaces([]);
              setPage((value) => Math.max(0, value - 1));
            }}
            disabled={page === 0 || loading}
          >
            上一頁
          </button>
          <span>
            第 {page + 1} 頁／共 {Math.ceil(totalCount / PAGE_SIZE)} 頁（{totalCount} 筆）
          </span>
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              setSelectedPlaces([]);
              setPage((value) => value + 1);
            }}
            disabled={!hasMore || loading}
          >
            下一頁
          </button>
        </nav>
      ) : null}
      <AppConfirmDialog
        open={placeToDelete !== null || confirmBulkDelete}
        title={
          confirmBulkDelete
            ? `永久刪除已選取的 ${selectedPlaces.length} 筆資料？`
            : "永久刪除觀光署來源資料？"
        }
        message={
          confirmBulkDelete ? (
            <>
              <p>這些來源資料不會因重新匯入而復原；已連結的 BiteMap 店家會保留。</p>
              <ul>
                {selectedPlaces.map((place) => (
                  <li key={place.id}>
                    {place.name} — {place.address ?? "尚無地址"}
                  </li>
                ))}
              </ul>
            </>
          ) : placeToDelete ? (
            `確定刪除「${placeToDelete.name}」${placeToDelete.address ? `（${placeToDelete.address}）` : ""}？此資料不會因重新匯入而復原。${placeToDelete.linked_restaurant_id ? "已連結的 BiteMap 店家會保留。" : ""}`
          ) : (
            ""
          )
        }
        confirmLabel={confirmBulkDelete ? `刪除 ${selectedPlaces.length} 筆` : "永久刪除"}
        danger
        onCancel={() => {
          setPlaceToDelete(null);
          setConfirmBulkDelete(false);
        }}
        onConfirm={() => {
          if (confirmBulkDelete) void deleteSelectedPlaces();
          else {
            const place = placeToDelete;
            if (place) void deletePlace(place);
          }
        }}
      />
    </section>
  );
}
