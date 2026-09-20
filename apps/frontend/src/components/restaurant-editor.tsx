"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { CoordinatePicker } from "@/components/coordinate-picker";
import { Icon } from "@/components/icons";
import {
  AdminApiError,
  Cuisine,
  PriceRange,
  Restaurant,
  adminApi,
  priceRangeLabels,
} from "@/lib/admin-api";

const emptyForm = {
  name: "",
  address: "",
  menuUrl: "",
  primaryCuisineId: "",
  priceRange: "" as PriceRange | "",
  latitude: null as number | null,
  longitude: null as number | null,
};

export function RestaurantEditor({ restaurantId }: { restaurantId?: string }) {
  const router = useRouter();
  const [form, setForm] = useState(emptyForm);
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [cuisines, setCuisines] = useState<Cuisine[]>([]);
  const [loading, setLoading] = useState(Boolean(restaurantId));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const reverseGeocodeRequestRef = useRef(0);
  const reverseGeocodeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    adminApi<Cuisine[]>("/cuisines").then((items) =>
      setCuisines(items.filter((item) => item.is_active)),
    );
    if (!restaurantId) return;
    adminApi<Restaurant>(`/restaurants/${restaurantId}`)
      .then((item) => {
        setRestaurant(item);
        setForm({
          name: item.name,
          address: item.address,
          menuUrl: item.menu_url ?? "",
          primaryCuisineId: item.primary_cuisine_id ?? "",
          priceRange: item.price_range ?? "",
          latitude: item.latitude,
          longitude: item.longitude,
        });
      })
      .catch(() => setMessage("無法載入店家資料。"))
      .finally(() => setLoading(false));
  }, [restaurantId]);

  function payload() {
    return {
      name: form.name,
      address: form.address,
      menu_url: form.menuUrl || null,
      primary_cuisine_id: form.primaryCuisineId || null,
      price_range: form.priceRange || null,
      latitude: form.latitude,
      longitude: form.longitude,
    };
  }

  async function persist(): Promise<Restaurant> {
    const result = restaurant
      ? await adminApi<Restaurant>(`/restaurants/${restaurant.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload()),
        })
      : await adminApi<Restaurant>("/restaurants", {
          method: "POST",
          body: JSON.stringify(payload()),
        });
    setRestaurant(result);
    if (!restaurant) router.replace(`/admin/restaurants/${result.id}`);
    return result;
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await persist();
      setMessage("草稿已儲存。 ");
    } catch {
      setMessage("無法儲存，請檢查欄位內容。 ");
    } finally {
      setSaving(false);
    }
  }

  async function publish() {
    setSaving(true);
    setMessage("");
    try {
      const saved = await persist();
      const published = await adminApi<Restaurant>(`/restaurants/${saved.id}/publish`, {
        method: "POST",
      });
      setRestaurant(published);
      setMessage("店家已發布，可供後續公開地圖查詢。 ");
    } catch (caught) {
      if (caught instanceof AdminApiError && caught.status === 422) {
        setMessage("發布前必須完成座標、主要料理與價格區間。 ");
      } else {
        setMessage("發布失敗，請稍後再試。 ");
      }
    } finally {
      setSaving(false);
    }
  }

  async function archive() {
    if (!restaurant) return;
    setSaving(true);
    try {
      const archived = await adminApi<Restaurant>(`/restaurants/${restaurant.id}/archive`, {
        method: "POST",
      });
      setRestaurant(archived);
      setMessage("店家已封存，不會出現在公開地圖。 ");
    } finally {
      setSaving(false);
    }
  }

  async function restore() {
    if (!restaurant) return;
    setSaving(true);
    try {
      const restored = await adminApi<Restaurant>(`/restaurants/${restaurant.id}/restore`, {
        method: "POST",
      });
      setRestaurant(restored);
      setMessage("店家已解封，現在可以編輯或重新發布。 ");
    } finally {
      setSaving(false);
    }
  }

  async function geocode() {
    setMessage("");
    try {
      const result = await adminApi<{
        candidates: Array<{ label: string; latitude: number; longitude: number }>;
      }>("/geocode", {
        method: "POST",
        body: JSON.stringify({ address: form.address }),
      });
      const candidate = result.candidates[0];
      if (candidate) {
        setForm((current) => ({
          ...current,
          address: current.address,
          latitude: candidate.latitude,
          longitude: candidate.longitude,
        }));
        setMessage("地址已定位，請確認地圖上的圖釘位置。 ");
      } else {
        setMessage("找不到地址，請改用地圖點選。 ");
      }
    } catch (caught) {
      if (caught instanceof AdminApiError && caught.status === 503) {
        setMessage("地址定位服務尚未設定，請直接在地圖上點選並拖曳圖釘。 ");
      } else {
        setMessage("地址定位失敗，請改用地圖點選。 ");
      }
    }
  }

  async function synchronizeAddress(latitude: number, longitude: number) {
    setForm((current) => ({ ...current, latitude, longitude }));
    if (reverseGeocodeTimerRef.current) clearTimeout(reverseGeocodeTimerRef.current);
    reverseGeocodeTimerRef.current = setTimeout(async () => {
      const requestId = ++reverseGeocodeRequestRef.current;
      try {
        const result = await adminApi<{ address: string | null }>("/geocode/reverse", {
          method: "POST",
          body: JSON.stringify({ latitude, longitude }),
        });
        if (requestId !== reverseGeocodeRequestRef.current) return;
        if (result.address) {
          setForm((current) => ({ ...current, address: result.address ?? current.address }));
          setMessage("地圖位置已同步到地址。 ");
        } else {
          setMessage("座標已更新，但找不到對應地址，請確認地址欄位。 ");
        }
      } catch {
        if (requestId === reverseGeocodeRequestRef.current) {
          setMessage("座標已更新，但地址同步失敗，請手動確認地址。 ");
        }
      }
    }, 1000);
  }

  if (loading) {
    return <main className="admin-page table-skeleton" aria-busy="true" />;
  }

  const selectedCuisine = cuisines.find((item) => item.id === form.primaryCuisineId);

  return (
    <main className="admin-page editor-page">
      <header className="admin-page__header">
        <div>
          <Link href="/admin/restaurants" className="back-link">
            <Icon name="back" /> 返回店家清單
          </Link>
          <h1>{restaurant ? "編輯店家" : "新增店家"}</h1>
          <p>先儲存草稿，確認必要資料後再發布。</p>
        </div>
        {restaurant ? (
          <span className={`status-badge is-${restaurant.status}`}>
            {restaurant.status === "published"
              ? "已發布"
              : restaurant.status === "archived"
                ? "已封存"
                : "草稿"}
          </span>
        ) : null}
      </header>

      <form onSubmit={save} className="restaurant-editor">
        <section className="editor-form" aria-labelledby="restaurant-details">
          <h2 id="restaurant-details">店家資料</h2>
          <div className="form-grid">
            <label className="form-grid__wide">
              店家名稱
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </label>
            <label className="form-grid__wide">
              地址
              <span className="input-action">
                <input
                  value={form.address}
                  onChange={(event) => setForm({ ...form, address: event.target.value })}
                  required
                />
                <button type="button" className="button button--quiet" onClick={geocode}>
                  地址定位
                </button>
              </span>
            </label>
            <label className="form-grid__wide">
              菜單網址（可選）
              <input
                type="url"
                placeholder="https://example.com/menu"
                value={form.menuUrl}
                onChange={(event) => setForm({ ...form, menuUrl: event.target.value })}
              />
              <small className="field-hint">
                目前先支援外部菜單連結，圖片/PDF 菜單後續再擴充。
              </small>
            </label>
            <label>
              主要料理
              <select
                value={form.primaryCuisineId}
                onChange={(event) => setForm({ ...form, primaryCuisineId: event.target.value })}
              >
                <option value="">尚未設定</option>
                {cuisines.map((cuisine) => (
                  <option key={cuisine.id} value={cuisine.id}>
                    {cuisine.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              價格區間
              <select
                value={form.priceRange}
                onChange={(event) =>
                  setForm({ ...form, priceRange: event.target.value as PriceRange | "" })
                }
              >
                <option value="">尚未設定</option>
                {Object.entries(priceRangeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="map-section">
            <div>
              <h2>店家座標</h2>
              <p>地圖點選與圖釘拖曳都會更新下方座標。</p>
            </div>
            <CoordinatePicker
              latitude={form.latitude}
              longitude={form.longitude}
              onChange={synchronizeAddress}
            />
            <div className="coordinate-values" aria-live="polite">
              <span>緯度 {form.latitude?.toFixed(6) ?? "尚未設定"}</span>
              <span>經度 {form.longitude?.toFixed(6) ?? "尚未設定"}</span>
            </div>
          </div>
        </section>

        <aside className="editor-summary">
          <h2>發布前確認</h2>
          <dl>
            <div>
              <dt>地址</dt>
              <dd>{form.address || "尚未填寫"}</dd>
            </div>
            <div>
              <dt>菜單</dt>
              <dd>{form.menuUrl ? "已設定網址" : "尚未設定"}</dd>
            </div>
            <div>
              <dt>座標</dt>
              <dd>{form.latitude !== null ? "已設定" : "尚未設定"}</dd>
            </div>
            <div>
              <dt>主要料理</dt>
              <dd>{selectedCuisine?.display_name ?? "尚未設定"}</dd>
            </div>
            <div>
              <dt>價格</dt>
              <dd>{form.priceRange ? priceRangeLabels[form.priceRange] : "尚未設定"}</dd>
            </div>
          </dl>
          {message ? (
            <p className="form-message" role="status">
              {message}
            </p>
          ) : null}
          <div className="editor-actions">
            <button className="button button--secondary" type="submit" disabled={saving}>
              {saving ? "處理中…" : "儲存草稿"}
            </button>
            <button
              className="button button--primary"
              type="button"
              onClick={publish}
              disabled={saving || restaurant?.status === "archived"}
            >
              發布店家
            </button>
            {restaurant && restaurant.status !== "archived" ? (
              <button className="button button--danger-text" type="button" onClick={archive}>
                封存店家
              </button>
            ) : null}
            {restaurant?.status === "archived" ? (
              <button className="button button--secondary" type="button" onClick={restore}>
                解封店家
              </button>
            ) : null}
          </div>
        </aside>
      </form>
    </main>
  );
}
