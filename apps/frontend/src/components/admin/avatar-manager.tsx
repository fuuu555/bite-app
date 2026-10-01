"use client";

import { Icon } from "@/components/admin/icons";
import { AdminApiError, adminApi, AvatarAsset } from "@/lib/admin-api";
import { FormEvent, useEffect, useState } from "react";

function formatFileSize(bytes: number) {
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function AvatarManager() {
  const [assets, setAssets] = useState<AvatarAsset[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [draftNames, setDraftNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const nextAssets = await adminApi<AvatarAsset[]>("/avatar-assets");
    setAssets(nextAssets);
    setDraftNames(Object.fromEntries(nextAssets.map((asset) => [asset.id, asset.display_name])));
  }

  useEffect(() => {
    let active = true;
    adminApi<AvatarAsset[]>("/avatar-assets")
      .then((nextAssets) => {
        if (!active) return;
        setAssets(nextAssets);
        setDraftNames(
          Object.fromEntries(nextAssets.map((asset) => [asset.id, asset.display_name])),
        );
      })
      .catch(() => {
        if (active) setError("無法載入頭貼資產，請確認 API 狀態。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("請先選擇 JPG、PNG 或 WebP 圖片。 ");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    const formData = new FormData();
    formData.append("display_name", displayName);
    formData.append("file", file);
    try {
      await adminApi<AvatarAsset>("/avatar-assets", { method: "POST", body: formData });
      await refresh();
      setDisplayName("");
      setFile(null);
      event.currentTarget.reset();
      setMessage("頭貼已加入資產庫，使用者現在可以選擇。 ");
    } catch (caught) {
      setError(
        caught instanceof AdminApiError && typeof caught.detail === "string"
          ? caught.detail
          : "頭貼上傳失敗，請檢查格式與檔案大小。",
      );
    } finally {
      setBusy(false);
    }
  }

  async function updateAsset(asset: AvatarAsset, values: Partial<AvatarAsset>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await adminApi<AvatarAsset>(`/avatar-assets/${asset.id}`, {
        method: "PATCH",
        body: JSON.stringify(values),
      });
      await refresh();
      setMessage(
        values.is_active === false ? "頭貼已停用，既有使用者仍可繼續顯示。" : "頭貼設定已更新。 ",
      );
    } catch {
      setError("頭貼設定更新失敗，請稍後再試。 ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="admin-page avatar-admin-page">
      <header className="admin-page__header">
        <div>
          <h1>頭貼資產</h1>
          <p>管理使用者可以選擇的內建頭貼。檔案目前保存在本地 media 資料夾。</p>
        </div>
      </header>

      <section className="avatar-upload-card" aria-labelledby="avatar-upload-title">
        <div>
          <span className="admin-section-kicker">LOCAL MEDIA</span>
          <h2 id="avatar-upload-title">新增一個內建頭貼</h2>
          <p>只接受 JPG、PNG、WebP，單檔上限 5 MB。未來可直接替換成 S3 儲存。</p>
        </div>
        <form className="avatar-upload-form" onSubmit={upload}>
          <label>
            頭貼名稱
            <input
              required
              maxLength={80}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="例如：午後橘貓"
            />
          </label>
          <label>
            圖片檔案
            <input
              required
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="button button--primary" type="submit" disabled={busy}>
            <Icon name="plus" />
            {busy ? "處理中…" : "上傳頭貼"}
          </button>
        </form>
      </section>

      {message ? <p className="form-message">{message}</p> : null}
      {error ? <p className="form-message is-error">{error}</p> : null}

      {loading ? (
        <div className="table-skeleton" aria-label="載入頭貼" aria-busy="true" />
      ) : assets.length === 0 ? (
        <section className="empty-state avatar-empty-state">
          <Icon name="user" />
          <h2>還沒有內建頭貼</h2>
          <p>上傳第一張後，使用者就能在個人設定中選擇。</p>
        </section>
      ) : (
        <section className="avatar-asset-grid" aria-label="頭貼資產列表">
          {assets.map((asset) => (
            <article
              className={`avatar-asset-card${asset.is_active ? "" : " is-inactive"}`}
              key={asset.id}
            >
              <div className="avatar-asset-card__preview">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={asset.url} alt="" />
                <span>{asset.is_active ? "可供選擇" : "已停用"}</span>
              </div>
              <div className="avatar-asset-card__body">
                <label>
                  名稱
                  <input
                    value={draftNames[asset.id] ?? asset.display_name}
                    maxLength={80}
                    onChange={(event) =>
                      setDraftNames((current) => ({ ...current, [asset.id]: event.target.value }))
                    }
                  />
                </label>
                <small>
                  {asset.mime_type} · {formatFileSize(asset.file_size)}
                </small>
                <div className="avatar-asset-card__actions">
                  <button
                    type="button"
                    className="button button--quiet"
                    disabled={busy || !draftNames[asset.id]?.trim()}
                    onClick={() => void updateAsset(asset, { display_name: draftNames[asset.id] })}
                  >
                    儲存名稱
                  </button>
                  <button
                    type="button"
                    className="button button--quiet"
                    disabled={busy}
                    onClick={() => void updateAsset(asset, { is_active: !asset.is_active })}
                  >
                    {asset.is_active ? "停用" : "重新啟用"}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
