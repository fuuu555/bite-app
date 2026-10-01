"use client";

import { IconArrowLeft, IconCheck, IconDeviceDesktop, IconPlus, IconX } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  AvatarAsset,
  MyProfile,
  UserApiError,
  fetchAvatarAssets,
  UserSession,
  suggestedProfileTags,
  userApi,
} from "@/lib/user-api";

export function ProfileSettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [avatarAssetId, setAvatarAssetId] = useState<string | null>(null);
  const [avatarAssets, setAvatarAssets] = useState<AvatarAsset[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [tagNotice, setTagNotice] = useState("");
  const [recentlyAddedTag, setRecentlyAddedTag] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!tagNotice) return;
    const timeout = window.setTimeout(() => setTagNotice(""), 2200);
    return () => window.clearTimeout(timeout);
  }, [tagNotice]);

  useEffect(() => {
    if (!recentlyAddedTag) return;
    const timeout = window.setTimeout(() => setRecentlyAddedTag(""), 550);
    return () => window.clearTimeout(timeout);
  }, [recentlyAddedTag]);

  useEffect(() => {
    Promise.all([
      userApi<MyProfile>("/me/profile"),
      userApi<UserSession[]>("/me/sessions"),
      fetchAvatarAssets(),
    ])
      .then(([loadedProfile, loadedSessions, loadedAvatarAssets]) => {
        setProfile(loadedProfile);
        setDisplayName(loadedProfile.display_name);
        setBio(loadedProfile.bio ?? "");
        setAvatarUrl(
          loadedProfile.avatar_source === "builtin" ? "" : (loadedProfile.avatar_url ?? ""),
        );
        setAvatarAssetId(loadedProfile.avatar_asset_id);
        setAvatarAssets(loadedAvatarAssets);
        setTags(loadedProfile.tags.map((tag) => tag.display_name));
        setSessions(loadedSessions);
      })
      .catch((caught) => {
        if (caught instanceof UserApiError && caught.status === 401) {
          router.replace("/login");
          return;
        }
        setError("目前無法載入設定，請稍後再試。");
      });
  }, [router]);

  function addTag(value: string) {
    const normalized = value.trim();
    if (!normalized) return;
    if (tags.includes(normalized)) {
      setTagNotice(`「${normalized}」已經加入。`);
      setNewTag("");
      return;
    }
    if (tags.length >= 8) {
      setTagNotice("最多可以選擇 8 個 Tag。");
      return;
    }
    setTags((current) => [...current, normalized]);
    setRecentlyAddedTag(normalized);
    setTagNotice(`已加入「${normalized}」，儲存後就會套用。`);
    setNewTag("");
  }

  function removeTag(value: string) {
    setTags((current) => current.filter((item) => item !== value));
    setRecentlyAddedTag("");
    setTagNotice(`已移除「${value}」。`);
  }

  function toggleTag(value: string) {
    // Suggested tags share the same draft state as custom tags and are persisted on save.
    // 常用與自訂 Tag 共用表單草稿，按下儲存後才會寫入個人資料。
    if (tags.includes(value)) {
      removeTag(value);
      return;
    }
    addTag(value);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const updated = await userApi<MyProfile>("/me/profile", {
        method: "PATCH",
        body: JSON.stringify({
          display_name: displayName,
          bio: bio || null,
          avatar_url: avatarUrl || null,
          avatar_asset_id: avatarAssetId,
          tags,
        }),
      });
      setProfile(updated);
      setTags(updated.tags.map((tag) => tag.display_name));
      setMessage("個人資料已更新。");
    } catch (caught) {
      setError(
        caught instanceof UserApiError && caught.status === 422
          ? "請檢查欄位格式。"
          : "儲存失敗，請稍後再試。",
      );
    } finally {
      setSaving(false);
    }
  }

  async function revokeSession(sessionId: string) {
    await userApi<void>(`/me/sessions/${sessionId}`, { method: "DELETE" });
    setSessions((current) => current.filter((item) => item.id !== sessionId));
  }

  if (error && !profile) {
    return (
      <main className="profile-state">
        <p>{error}</p>
      </main>
    );
  }
  if (!profile) {
    return (
      <main className="profile-state is-loading">
        <p>正在載入個人設定…</p>
      </main>
    );
  }

  return (
    <main className="profile-settings-page" aria-labelledby="profile-settings-title">
      <header className="profile-settings-page__header">
        <Link className="back-link" href="/profile">
          <IconArrowLeft aria-hidden="true" /> 返回個人頁面
        </Link>
        <h1 id="profile-settings-title">個人設定</h1>
      </header>

      <div className="profile-settings-layout">
        <form className="profile-settings-card" onSubmit={save}>
          <div className="profile-settings-card__heading">
            <div>
              <h2>公開資料</h2>
              <p>其他使用者會看到名稱、簡介、頭像與 Tag。</p>
            </div>
            <span className="profile-settings-avatar-fallback">{displayName.slice(0, 1)}</span>
          </div>
          <label>
            名稱
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              maxLength={80}
              required
            />
          </label>
          <label>
            自我介紹
            <textarea
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              maxLength={500}
              rows={4}
            />
          </label>
          <label>
            頭像網址
            <input
              type="url"
              value={avatarUrl}
              onChange={(event) => {
                setAvatarUrl(event.target.value);
                setAvatarAssetId(null);
              }}
              placeholder="https://…"
            />
            <span className="field-hint">僅支援安全的 HTTPS 圖片網址。</span>
          </label>
          <section className="profile-avatar-picker" aria-labelledby="profile-avatar-picker-title">
            <div className="profile-avatar-picker__heading">
              <div>
                <span className="profile-settings-label" id="profile-avatar-picker-title">
                  內建頭貼
                </span>
                <p>選擇 BiteMap 提供的頭貼。</p>
              </div>
              {avatarAssetId ? (
                <span className="profile-avatar-picker__selected">已選擇</span>
              ) : null}
            </div>
            {avatarAssets.length > 0 ? (
              <div className="profile-avatar-options">
                {avatarAssets.map((asset) => (
                  <button
                    type="button"
                    key={asset.id}
                    className={avatarAssetId === asset.id ? "is-selected" : undefined}
                    onClick={() => {
                      setAvatarAssetId(asset.id);
                      setAvatarUrl("");
                    }}
                    aria-pressed={avatarAssetId === asset.id}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={asset.url} alt="" />
                    <span>{asset.display_name}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="profile-avatar-picker__empty">管理員尚未提供內建頭貼。</p>
            )}
          </section>
          <div className="profile-settings-tags">
            <div className="profile-tag-section-heading">
              <div>
                <span className="profile-settings-label">美食 Tag</span>
                <p>選幾個標籤，讓大家更快認識你的口味。</p>
              </div>
              <span className="profile-tag-count">{tags.length}/8</span>
            </div>

            <section className="profile-tag-selection" aria-label="已選擇的美食 Tag">
              <div className="profile-tag-selection__heading">
                <span>已選 Tag</span>
                {tags.length ? <small>點擊標籤上的 × 移除</small> : null}
              </div>
              {tags.length ? (
                <div className="profile-tags profile-tags--selected">
                  {tags.map((tag) => (
                    <button
                      className={`profile-tag profile-tag--button${
                        recentlyAddedTag === tag ? " is-new" : ""
                      }`}
                      type="button"
                      key={tag}
                      onClick={() => removeTag(tag)}
                      aria-label={`移除 ${tag}`}
                    >
                      <IconCheck aria-hidden="true" /> {tag} <IconX aria-hidden="true" />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="profile-tag-selection__empty">還沒有選擇，從下方常用 Tag 開始吧。</p>
              )}
            </section>

            <section className="profile-tag-picker" aria-label="常用美食 Tag">
              <div className="profile-tag-picker__heading">
                <div>
                  <strong>常用 Tag</strong>
                  <p>點一下就能加入，已選的會標示完成。</p>
                </div>
                <span className="profile-tag-picker__hint">最多 8 個</span>
              </div>
              <div className="profile-tag-options">
                {suggestedProfileTags.map((tag) => {
                  const selected = tags.includes(tag);
                  return (
                    <button
                      className={`profile-tag-option${selected ? " is-selected" : ""}`}
                      type="button"
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      aria-pressed={selected}
                    >
                      <span className="profile-tag-option__icon" aria-hidden="true">
                        {selected ? <IconCheck /> : <IconPlus />}
                      </span>
                      <span>{tag}</span>
                    </button>
                  );
                })}
              </div>
            </section>

            <div className="profile-tag-custom">
              <div className="profile-tag-custom__heading">
                <strong>找不到想要的？自己新增</strong>
                <span>最多 40 個字</span>
              </div>
              <div className="profile-tag-adder">
                <input
                  value={newTag}
                  onChange={(event) => setNewTag(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addTag(newTag);
                    }
                  }}
                  placeholder="例如：深夜食堂派"
                  maxLength={40}
                  aria-label="自訂 Tag"
                />
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => addTag(newTag)}
                  disabled={!newTag.trim() || tags.length >= 8}
                >
                  <IconPlus aria-hidden="true" /> 加入
                </button>
              </div>
            </div>
            {tagNotice ? (
              <p className="profile-tag-toast" role="status" aria-live="polite">
                <IconCheck aria-hidden="true" /> {tagNotice}
              </p>
            ) : null}
          </div>
          {message ? (
            <p className="form-message" role="status">
              {message}
            </p>
          ) : null}
          {error ? (
            <p className="form-message is-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button button--primary" type="submit" disabled={saving}>
            {saving ? "儲存中…" : "儲存變更"}
          </button>
        </form>

        <aside className="profile-settings-side">
          <section className="profile-settings-card profile-sessions-card">
            <div className="profile-settings-card__heading">
              <div>
                <h2>登入裝置</h2>
                <p>可以隨時撤銷其他裝置的 Session。</p>
              </div>
              <IconDeviceDesktop aria-hidden="true" />
            </div>
            <ul className="profile-session-list">
              {sessions.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.current ? "目前裝置" : item.device_label}</strong>
                    <small>最近使用：{new Date(item.last_seen_at).toLocaleString("zh-TW")}</small>
                  </div>
                  {item.current ? (
                    <span className="profile-session-current">使用中</span>
                  ) : (
                    <button type="button" onClick={() => revokeSession(item.id)}>
                      登出
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </main>
  );
}
