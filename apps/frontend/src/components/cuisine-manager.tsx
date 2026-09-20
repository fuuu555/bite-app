"use client";

import { FormEvent, useEffect, useState } from "react";

import { Cuisine, adminApi } from "@/lib/admin-api";

const colorOptions = ["#F26B4F", "#E7B75A", "#4E8F6B", "#4277A6", "#A74A5B"];
const iconOptions = [
  { value: "rice-bowl", label: "飯碗" },
  { value: "burger", label: "漢堡" },
  { value: "leaf", label: "葉片" },
  { value: "fish", label: "魚" },
  { value: "coffee", label: "咖啡" },
];

const iconGlyphs: Record<string, string> = {
  "rice-bowl": "🍚",
  burger: "🍔",
  leaf: "🥬",
  fish: "🐟",
  coffee: "☕",
};
const CUISINES_PER_PAGE = 8;

const cuisineSlugPresets: Record<string, string> = {
  台灣料理: "taiwanese",
  牛肉麵: "beef-noodles",
  咖啡: "coffee",
  漢堡: "burger",
  日本料理: "japanese",
  韓式料理: "korean",
  義大利料理: "italian",
  火鍋: "hot-pot",
  早餐: "breakfast",
  甜點: "desserts",
  飲料: "drinks",
};

function generateSlug(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed) return "";
  if (cuisineSlugPresets[trimmed]) return cuisineSlugPresets[trimmed];

  const latin = trimmed
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (latin) return latin;

  // 中文名稱沒有固定翻譯時，產生穩定短碼，仍可在進階設定手動調整。
  const hash = [...trimmed].reduce(
    (total, character) => (total * 31 + character.codePointAt(0)!) >>> 0,
    7,
  );
  return `cuisine-${hash.toString(36)}`;
}

export function CuisineManager() {
  const [cuisines, setCuisines] = useState<Cuisine[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [color, setColor] = useState(colorOptions[0]);
  const [iconKey, setIconKey] = useState(iconOptions[0].value);
  const [message, setMessage] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingDisplayName, setEditingDisplayName] = useState("");
  const [editingColor, setEditingColor] = useState(colorOptions[0]);
  const [editingIconKey, setEditingIconKey] = useState(iconOptions[0].value);

  async function load(): Promise<Cuisine[]> {
    try {
      const data = await adminApi<Cuisine[]>("/cuisines");
      setCuisines(data);
      return data;
    } catch {
      setMessage("無法載入料理分類。");
      return [];
    }
  }

  useEffect(() => {
    let active = true;
    adminApi<Cuisine[]>("/cuisines")
      .then((data) => {
        if (active) setCuisines(data);
      })
      .catch(() => {
        if (active) setMessage("無法載入料理分類。");
      });
    return () => {
      active = false;
    };
  }, []);

  const pageCount = Math.max(1, Math.ceil(cuisines.length / CUISINES_PER_PAGE));
  const safeCurrentPage = Math.min(currentPage, pageCount);
  const visibleCuisines = cuisines.slice(
    (safeCurrentPage - 1) * CUISINES_PER_PAGE,
    safeCurrentPage * CUISINES_PER_PAGE,
  );

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    try {
      const created = await adminApi<Cuisine>("/cuisines", {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName,
          slug,
          color,
          icon_key: iconKey,
        }),
      });
      setDisplayName("");
      setSlug("");
      setSlugEdited(false);
      const nextCuisines = await load();
      const createdIndex = nextCuisines.findIndex((cuisine) => cuisine.id === created.id);
      if (createdIndex >= 0) {
        setCurrentPage(Math.floor(createdIndex / CUISINES_PER_PAGE) + 1);
      }
    } catch {
      setMessage("無法新增分類，請確認識別名稱沒有重複。 ");
    }
  }

  async function toggle(cuisine: Cuisine) {
    await adminApi<Cuisine>(`/cuisines/${cuisine.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !cuisine.is_active }),
    });
    await load();
  }

  async function remove(cuisine: Cuisine) {
    if (!window.confirm(`確定要刪除「${cuisine.display_name}」嗎？此操作無法復原。`)) return;
    setMessage("");
    try {
      await adminApi<void>(`/cuisines/${cuisine.id}`, { method: "DELETE" });
      await load();
    } catch {
      setMessage("無法刪除分類；若分類仍被店家使用，請先停用或移除店家關聯。 ");
    }
  }

  function startEditing(cuisine: Cuisine) {
    setEditingId(cuisine.id);
    setEditingDisplayName(cuisine.display_name);
    setEditingColor(cuisine.color);
    setEditingIconKey(cuisine.icon_key);
    setMessage("");
  }

  function cancelEditing() {
    setEditingId(null);
  }

  async function update(cuisine: Cuisine) {
    setMessage("");
    try {
      await adminApi<Cuisine>(`/cuisines/${cuisine.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          display_name: editingDisplayName,
          color: editingColor,
          icon_key: editingIconKey,
        }),
      });
      setEditingId(null);
      await load();
    } catch {
      setMessage("無法更新分類，請確認欄位內容。 ");
    }
  }

  return (
    <main className="admin-page">
      <header className="admin-page__header">
        <div>
          <h1>料理分類</h1>
          <p>標記色只區分料理類型，並以圖示與文字提供輔助辨識。</p>
        </div>
      </header>
      <div className="cuisine-manager-layout">
        <form className="settings-form cuisine-create-card" onSubmit={create}>
          <h2>新增分類</h2>
          <div className="cuisine-create-fields">
            <label>
              顯示名稱
              <input
                value={displayName}
                onChange={(event) => {
                  const value = event.target.value;
                  setDisplayName(value);
                  if (!slugEdited) setSlug(generateSlug(value));
                }}
                required
              />
            </label>
            <details className="advanced-settings">
              <summary>進階設定：系統識別碼</summary>
              <label>
                系統識別碼
                <input
                  value={slug}
                  onChange={(event) => {
                    setSlugEdited(true);
                    setSlug(event.target.value.toLowerCase());
                  }}
                  pattern="[a-z0-9-]+"
                  placeholder="taiwanese"
                  required
                />
                <small className="field-hint">
                  由顯示名稱自動產生，建立後請避免修改；只能使用小寫英數字與連字號。
                </small>
              </label>
            </details>
            <fieldset>
              <legend>固定色票</legend>
              <div className="color-options">
                {colorOptions.map((option) => (
                  <label key={option} title={option}>
                    <input
                      type="radio"
                      name="color"
                      value={option}
                      checked={color === option}
                      onChange={() => setColor(option)}
                    />
                    <span style={{ background: option }} />
                  </label>
                ))}
              </div>
              <label className="custom-color-option">
                自訂顏色
                <input
                  type="color"
                  value={color}
                  onChange={(event) => setColor(event.target.value.toUpperCase())}
                  aria-label="自訂料理分類顏色"
                />
                <span>{color}</span>
              </label>
            </fieldset>
            <label>
              圖示
              <select value={iconKey} onChange={(event) => setIconKey(event.target.value)}>
                {iconOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button className="button button--primary" type="submit">
              新增料理分類
            </button>
          </div>
          {message ? <p className="form-message is-error">{message}</p> : null}
        </form>
        <section className="cuisine-list" aria-label="料理分類清單">
          <h2>目前分類</h2>
          <div className="cuisine-list__items">
            {visibleCuisines.map((cuisine) => (
              <article key={cuisine.id} className={!cuisine.is_active ? "is-disabled" : undefined}>
                {editingId === cuisine.id ? (
                  <div className="cuisine-edit-form">
                    <label>
                      顯示名稱
                      <input
                        value={editingDisplayName}
                        onChange={(event) => setEditingDisplayName(event.target.value)}
                        required
                      />
                    </label>
                    <label>
                      色票
                      <input
                        type="color"
                        value={editingColor}
                        onChange={(event) => setEditingColor(event.target.value.toUpperCase())}
                        aria-label="編輯料理分類顏色"
                      />
                    </label>
                    <label>
                      圖示
                      <select
                        value={editingIconKey}
                        onChange={(event) => setEditingIconKey(event.target.value)}
                      >
                        {iconOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="cuisine-list__actions">
                      <button
                        type="button"
                        className="button button--primary"
                        onClick={() => update(cuisine)}
                      >
                        儲存
                      </button>
                      <button
                        type="button"
                        className="button button--quiet"
                        onClick={cancelEditing}
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <span className="cuisine-swatch" style={{ background: cuisine.color }} />
                    <span className="cuisine-icon" aria-label={`${cuisine.display_name}圖示`}>
                      {iconGlyphs[cuisine.icon_key] ?? "🍽️"}
                    </span>
                    <div className="cuisine-list__identity">
                      <strong>{cuisine.display_name}</strong>
                      <small>{cuisine.slug}</small>
                    </div>
                    <small className="cuisine-list__icon-name">Icon：{cuisine.icon_key}</small>
                    <div className="cuisine-list__actions">
                      <button
                        type="button"
                        className="button button--quiet"
                        onClick={() => startEditing(cuisine)}
                      >
                        編輯
                      </button>
                      <button
                        type="button"
                        className="button button--quiet"
                        onClick={() => toggle(cuisine)}
                      >
                        {cuisine.is_active ? "停用" : "啟用"}
                      </button>
                      <button
                        type="button"
                        className="button button--danger-quiet"
                        onClick={() => remove(cuisine)}
                      >
                        刪除
                      </button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
          {pageCount > 1 ? (
            <nav className="admin-pagination" aria-label="料理分類分頁">
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
        </section>
      </div>
    </main>
  );
}
