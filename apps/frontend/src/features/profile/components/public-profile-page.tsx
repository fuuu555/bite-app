"use client";

import {
  IconArrowLeft,
  IconDotsVertical,
  IconMessageCircle,
  IconTag,
  IconUserPlus,
  IconUserX,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createDirectConversation } from "@/features/chat/api/chat-api";
import {
  acceptFriendRequest,
  blockUser,
  cancelFriendRequest,
  followUser,
  rejectFriendRequest,
  removeFriend,
  sendFriendRequest,
  unfollowUser,
  unblockUser,
} from "@/features/profile/api/social-api";
import { Profile, UserApiError, userApi } from "@/shared/auth/user-api";
import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";

export function PublicProfilePage({ userId }: { userId: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [blockConfirmOpen, setBlockConfirmOpen] = useState(false);

  useEffect(() => {
    userApi<Profile>(`/profiles/${userId}`)
      .then(setProfile)
      .catch((caught) => {
        setError(
          caught instanceof UserApiError && caught.status === 404
            ? "找不到這個公開個人頁面。"
            : "目前無法載入公開個人頁面。",
        );
      });
  }, [userId]);

  async function applyAction(
    action: () => Promise<{ relationship: NonNullable<Profile["relationship"]> }>,
  ) {
    setBusy(true);
    setActionError("");
    try {
      const response = await action();
      setProfile((current) =>
        current ? { ...current, relationship: response.relationship } : current,
      );
    } catch (caught) {
      setActionError(
        caught instanceof UserApiError
          ? String(caught.detail || "操作失敗")
          : "操作失敗，請稍後再試。",
      );
    } finally {
      setBusy(false);
    }
  }

  async function openConversation() {
    setBusy(true);
    setActionError("");
    try {
      const conversation = await createDirectConversation(userId);
      router.push(`/chat?category=chat&conversation=${conversation.conversation_id}`);
    } catch (caught) {
      setActionError(
        caught instanceof UserApiError
          ? String(caught.detail || "目前無法開啟私訊")
          : "目前無法開啟私訊。",
      );
      setBusy(false);
    }
  }

  if (error) {
    return (
      <main className="profile-state">
        <p>{error}</p>
        <Link className="button button--secondary" href="/">
          回到探索
        </Link>
      </main>
    );
  }
  if (!profile) {
    return (
      <main className="profile-state is-loading">
        <p>正在載入公開個人頁面…</p>
      </main>
    );
  }

  return (
    <main className="public-profile-page" aria-labelledby="public-profile-title">
      <Link className="back-link" href="/">
        <IconArrowLeft aria-hidden="true" /> 回到探索
      </Link>
      <section className="public-profile-card">
        <div className="public-profile-card__top">
          {profile.avatar_url ? (
            // Remote avatar URLs stay unoptimized until signed object storage is introduced.
            // 遠端頭像網址在導入簽名物件儲存前不交給 Next Image 代理。
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
          )}
          <div>
            <h1 id="public-profile-title">{profile.display_name}</h1>
            <p>{profile.bio || "這位 BiteMap 使用者還沒有寫下自我介紹。"}</p>
          </div>
        </div>
        <div className="profile-tags" aria-label="美食興趣標籤">
          {profile.tags.map((tag) => (
            <span className="profile-tag" key={tag.id}>
              <IconTag aria-hidden="true" /> {tag.display_name}
            </span>
          ))}
        </div>
        {profile.relationship ? (
          <div className="public-profile-actions" aria-label="社交操作">
            {profile.relationship.can_message ? (
              <button
                type="button"
                className="button button--primary"
                disabled={busy}
                onClick={() => void openConversation()}
              >
                <IconMessageCircle aria-hidden="true" />
                {profile.relationship.status === "friends" ? "聊天" : "私聊"}
              </button>
            ) : null}
            {profile.relationship.can_add_friend ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() => void applyAction(() => sendFriendRequest(userId))}
              >
                <IconUserPlus aria-hidden="true" /> 加好友
              </button>
            ) : null}
            {profile.relationship.follow_status === "following" ||
            profile.relationship.follow_status === "mutual" ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() =>
                  void applyAction(async () => ({ relationship: await unfollowUser(userId) }))
                }
              >
                取消追蹤
              </button>
            ) : profile.relationship.status !== "blocked_by_me" &&
              profile.relationship.status !== "blocked_me" ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() =>
                  void applyAction(async () => ({ relationship: await followUser(userId) }))
                }
              >
                追蹤
              </button>
            ) : null}
            {profile.relationship.can_accept_friend_request && profile.relationship.request_id ? (
              <>
                <button
                  type="button"
                  className="button button--primary"
                  disabled={busy}
                  onClick={() =>
                    void applyAction(() => acceptFriendRequest(profile.relationship!.request_id!))
                  }
                >
                  接受好友邀請
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  disabled={busy}
                  onClick={() =>
                    void applyAction(() => rejectFriendRequest(profile.relationship!.request_id!))
                  }
                >
                  拒絕
                </button>
              </>
            ) : null}
            {profile.relationship.status === "outgoing_pending" &&
            profile.relationship.request_id ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() =>
                  void applyAction(() => cancelFriendRequest(profile.relationship!.request_id!))
                }
              >
                取消好友邀請
              </button>
            ) : null}
            {profile.relationship.status === "friends" ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() =>
                  void applyAction(async () => ({ relationship: await removeFriend(userId) }))
                }
              >
                <IconUserX aria-hidden="true" /> 移除好友
              </button>
            ) : null}
            {profile.relationship.status === "blocked_by_me" ? (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy}
                onClick={() =>
                  void applyAction(async () => ({ relationship: await unblockUser(userId) }))
                }
              >
                解除封鎖
              </button>
            ) : null}
            {profile.relationship.status !== "blocked_by_me" &&
            profile.relationship.status !== "blocked_me" ? (
              <div className="public-profile-actions__more">
                <button
                  type="button"
                  className="button button--ghost"
                  aria-expanded={moreOpen}
                  aria-haspopup="menu"
                  disabled={busy}
                  onClick={() => setMoreOpen((current) => !current)}
                >
                  <IconDotsVertical aria-hidden="true" /> 更多操作
                </button>
                {moreOpen ? (
                  <div className="public-profile-actions__menu" role="menu">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMoreOpen(false);
                        setBlockConfirmOpen(true);
                      }}
                    >
                      封鎖
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
        {actionError ? (
          <p className="form-message is-error" role="alert">
            {actionError}
          </p>
        ) : null}
      </section>
      <AppConfirmDialog
        open={blockConfirmOpen}
        title="封鎖使用者"
        message={`封鎖 ${profile.display_name} 後會解除好友、停止彼此私聊與追蹤。既有聊天紀錄會保留，確定要繼續嗎？`}
        confirmLabel="封鎖"
        danger
        onCancel={() => setBlockConfirmOpen(false)}
        onConfirm={() => {
          setBlockConfirmOpen(false);
          void applyAction(async () => ({ relationship: await blockUser(userId) }));
        }}
      />
    </main>
  );
}
