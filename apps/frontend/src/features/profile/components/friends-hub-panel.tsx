"use client";

import {
  IconCheck,
  IconClipboard,
  IconMessageCircle,
  IconSearch,
  IconShieldLock,
  IconUserPlus,
  IconUserX,
  IconX,
} from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";
import { createDirectConversation } from "@/features/chat/api/chat-api";
import {
  acceptFriendRequest,
  cancelFriendRequest,
  fetchFriends,
  lookupFriendCode,
  rejectFriendRequest,
  removeFriend,
  sendFriendRequest,
  type FriendRequest,
  type FriendSummary,
} from "@/features/profile/api/social-api";
import { useRealtime } from "@/shared/realtime/realtime";
import { MyProfile, Profile, UserApiError, userApi } from "@/shared/auth/user-api";

type FriendRequestProfile = Record<string, Profile | null>;

function FriendAvatar({
  profile,
}: {
  profile: Pick<FriendSummary, "avatar_url" | "display_name">;
}) {
  return profile.avatar_url ? (
    // Public profile URLs are already validated by the backend contract.
    // 公開個人資料網址已由後端契約驗證。
    // eslint-disable-next-line @next/next/no-img-element
    <img className="friends-hub-avatar" src={profile.avatar_url} alt="" />
  ) : (
    <span className="friends-hub-avatar friends-hub-avatar--fallback" aria-hidden="true">
      {profile.display_name.slice(0, 1)}
    </span>
  );
}

function requestTargetId(request: FriendRequest, currentUserId: string) {
  return request.requester_id === currentUserId ? request.recipient_id : request.requester_id;
}

export function FriendsHubPanel({ profile }: { profile: MyProfile }) {
  const router = useRouter();
  const { subscribe } = useRealtime();
  const [friends, setFriends] = useState<FriendSummary[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [requestProfiles, setRequestProfiles] = useState<FriendRequestProfile>({});
  const [code, setCode] = useState("");
  const [lookup, setLookup] = useState<Awaited<ReturnType<typeof lookupFriendCode>> | null>(null);
  const [lookupState, setLookupState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acceptStrangerMessages, setAcceptStrangerMessages] = useState(
    profile.accept_stranger_messages,
  );
  const [savingPrivacy, setSavingPrivacy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showAllFriends, setShowAllFriends] = useState(false);
  const [friendToRemove, setFriendToRemove] = useState<FriendSummary | null>(null);
  const noticeTimerRef = useRef<number | null>(null);

  function clearNoticeTimer() {
    if (noticeTimerRef.current !== null) {
      window.clearTimeout(noticeTimerRef.current);
      noticeTimerRef.current = null;
    }
  }

  function showNotice(message: string, transient = false) {
    clearNoticeTimer();
    setNotice(message);
    if (!transient) return;
    noticeTimerRef.current = window.setTimeout(() => {
      setNotice((current) => (current === message ? "" : current));
      noticeTimerRef.current = null;
    }, 2_000);
  }

  useEffect(
    () => () => {
      clearNoticeTimer();
    },
    [],
  );

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const [loadedFriends, loadedRequests] = await Promise.all([
          fetchFriends(signal),
          userApi<FriendRequest[]>("/friend-requests", { signal }),
        ]);
        const profiles = await Promise.all(
          loadedRequests.map(async (request) => {
            const targetId = requestTargetId(request, profile.id);
            try {
              return [
                targetId,
                await userApi<Profile>(`/profiles/${targetId}`, { signal }),
              ] as const;
            } catch {
              return [targetId, null] as const;
            }
          }),
        );
        setFriends(loadedFriends);
        setRequests(loadedRequests);
        setRequestProfiles(Object.fromEntries(profiles));
        setError("");
      } catch (caught) {
        if (!signal?.aborted) {
          setError(
            caught instanceof UserApiError && caught.status === 401
              ? "登入已過期，請重新登入。"
              : "好友資料暫時無法載入，請稍後重試。",
          );
        }
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [profile.id],
  );

  useEffect(() => {
    const controller = new AbortController();
    const initialTimer = window.setTimeout(() => void load(controller.signal), 0);
    const unsubscribe = subscribe("conversation-list", undefined, () => void load());
    return () => {
      window.clearTimeout(initialTimer);
      controller.abort();
      unsubscribe();
    };
  }, [load, subscribe]);

  const pendingIncoming = useMemo(
    () => requests.filter((request) => request.recipient_id === profile.id),
    [profile.id, requests],
  );
  const pendingOutgoing = useMemo(
    () => requests.filter((request) => request.requester_id === profile.id),
    [profile.id, requests],
  );
  // Keep the social hub compact until the user requests the complete list.
  // 社交中心預設精簡，使用者主動展開後才顯示完整好友名單。
  const visibleFriends = showAllFriends ? friends : friends.slice(0, 3);

  async function searchCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = code.replace(/\s/g, "");
    if (!/^\d{6}$/.test(normalized)) {
      setLookupState("error");
      setLookup(null);
      setError("好友碼需要是 6 位數字。");
      return;
    }
    setLookupState("loading");
    setError("");
    try {
      setLookup(await lookupFriendCode(normalized));
      setLookupState("ready");
    } catch (caught) {
      setLookup(null);
      setLookupState("error");
      setError(
        caught instanceof UserApiError && caught.status === 404
          ? "找不到這組好友碼。"
          : "好友碼查詢失敗，請稍後再試。",
      );
    }
  }

  async function addLookupFriend() {
    if (!lookup) return;
    try {
      await sendFriendRequest(lookup.id);
      showNotice("好友邀請已送出。", true);
      setLookup(null);
      setLookupState("idle");
      setCode("");
      await load();
    } catch {
      setError("好友邀請未能送出，請確認目前的關係狀態。");
    }
  }

  async function respond(requestId: string, accepted: boolean) {
    try {
      if (accepted) await acceptFriendRequest(requestId);
      else await rejectFriendRequest(requestId);
      showNotice(accepted ? "已接受好友邀請。" : "已拒絕好友邀請。", accepted);
      await load();
    } catch {
      setError("好友邀請狀態更新失敗，請稍後再試。");
    }
  }

  async function cancel(requestId: string) {
    try {
      await cancelFriendRequest(requestId);
      showNotice("已取消好友邀請。");
      await load();
    } catch {
      setError("取消好友邀請失敗，請稍後再試。");
    }
  }

  async function unfriend(friend: FriendSummary) {
    try {
      await removeFriend(friend.id);
      setFriendToRemove(null);
      showNotice("已解除好友。");
      await load();
    } catch {
      setError("解除好友失敗，請稍後再試。");
    }
  }

  async function openChat(friend: FriendSummary) {
    try {
      const conversation = await createDirectConversation(friend.id);
      router.push(`/chat?category=chat&conversation=${conversation.conversation_id}`);
    } catch {
      setError("聊天室目前無法開啟，請稍後再試。");
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(profile.friend_code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("無法複製好友碼，請手動記下。");
    }
  }

  async function updatePrivacy(checked: boolean) {
    setSavingPrivacy(true);
    setError("");
    try {
      const updated = await userApi<MyProfile>("/me/profile", {
        method: "PATCH",
        body: JSON.stringify({ accept_stranger_messages: checked }),
      });
      setAcceptStrangerMessages(updated.accept_stranger_messages);
      showNotice(checked ? "已開放陌生人私聊。" : "已關閉陌生人私聊。");
    } catch {
      setError("隱私設定更新失敗，請稍後再試。");
    } finally {
      setSavingPrivacy(false);
    }
  }

  return (
    <section className="friends-hub" aria-labelledby="friends-hub-title">
      <div className="friends-hub__heading">
        <div className="profile-section-title">
          <IconUserPlus aria-hidden="true" />
          <h2 id="friends-hub-title">好友管理</h2>
          <span>{friends.length} 位</span>
        </div>
        <p>管理好友關係與社交隱私；一對一對話請到「聊天」。</p>
      </div>

      <div className="friends-hub__code-card">
        <div>
          <span className="friends-hub__eyebrow">我的好友碼</span>
          <strong>
            {profile.friend_code.slice(0, 3)} {profile.friend_code.slice(3)}
          </strong>
        </div>
        <button type="button" className="button button--secondary" onClick={() => void copyCode()}>
          {copied ? <IconCheck aria-hidden="true" /> : <IconClipboard aria-hidden="true" />}
          {copied ? "已複製" : "複製"}
        </button>
      </div>

      <form className="friends-hub__search" onSubmit={(event) => void searchCode(event)}>
        <label htmlFor="friend-code-search">用好友碼找人</label>
        <div>
          <input
            id="friend-code-search"
            inputMode="numeric"
            maxLength={7}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/[^\d\s]/g, ""))}
            placeholder="輸入 6 位數好友碼"
          />
          <button
            type="submit"
            className="button button--primary"
            disabled={lookupState === "loading"}
          >
            <IconSearch aria-hidden="true" />
            {lookupState === "loading" ? "搜尋中…" : "搜尋"}
          </button>
        </div>
      </form>

      {lookup ? (
        <div className="friends-hub__lookup" role="status">
          <FriendAvatar profile={lookup} />
          <div>
            <strong>{lookup.display_name}</strong>
            <small>
              {lookup.relationship.status === "friends"
                ? "已經是好友"
                : lookup.relationship.status === "outgoing_pending"
                  ? "好友邀請已送出"
                  : lookup.relationship.status === "incoming_pending"
                    ? "對方已向你送出邀請"
                    : "可以送出好友邀請"}
            </small>
          </div>
          {lookup.relationship.can_add_friend ? (
            <button
              type="button"
              className="button button--secondary"
              onClick={() => void addLookupFriend()}
            >
              <IconUserPlus aria-hidden="true" /> 加好友
            </button>
          ) : null}
        </div>
      ) : null}

      {loading ? <p className="friends-hub__state">正在載入好友資料…</p> : null}
      {pendingIncoming.length > 0 ? (
        <section className="friends-hub__section" aria-labelledby="friend-requests-title">
          <div className="friends-hub__section-heading">
            <h3 id="friend-requests-title">好友邀請</h3>
            <span>{pendingIncoming.length} 筆待處理</span>
          </div>
          {pendingIncoming.map((request) => {
            const requester = requestProfiles[request.requester_id];
            return (
              <div className="friends-hub__request" key={request.id}>
                {requester ? (
                  <FriendAvatar profile={requester} />
                ) : (
                  <IconUserPlus aria-hidden="true" />
                )}
                <strong>{requester?.display_name ?? "一位使用者"}</strong>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => void respond(request.id, true)}
                >
                  <IconCheck aria-hidden="true" /> 接受
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void respond(request.id, false)}
                >
                  <IconX aria-hidden="true" /> 拒絕
                </button>
              </div>
            );
          })}
        </section>
      ) : null}

      {pendingOutgoing.length > 0 ? (
        <section className="friends-hub__section" aria-labelledby="outgoing-requests-title">
          <div className="friends-hub__section-heading">
            <h3 id="outgoing-requests-title">已送出的邀請</h3>
            <span>{pendingOutgoing.length} 筆</span>
          </div>
          {pendingOutgoing.map((request) => {
            const recipient = requestProfiles[request.recipient_id];
            return (
              <div className="friends-hub__request" key={request.id}>
                {recipient ? (
                  <FriendAvatar profile={recipient} />
                ) : (
                  <IconUserPlus aria-hidden="true" />
                )}
                <strong>{recipient?.display_name ?? "一位使用者"}</strong>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => void cancel(request.id)}
                >
                  <IconX aria-hidden="true" /> 取消
                </button>
              </div>
            );
          })}
        </section>
      ) : null}

      <section className="friends-hub__section" aria-labelledby="friends-list-title">
        <div className="friends-hub__section-heading">
          <h3 id="friends-list-title">好友名單</h3>
          <span>{friends.length} 位</span>
        </div>
        {friends.length > 0 ? (
          <div className="friends-hub__list" id="friends-list">
            {visibleFriends.map((friend) => (
              <div className="friends-hub__friend" key={friend.id}>
                <FriendAvatar profile={friend} />
                <strong>{friend.display_name}</strong>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => void openChat(friend)}
                >
                  <IconMessageCircle aria-hidden="true" /> 聊天室
                </button>
                <button
                  type="button"
                  className="button button--ghost friends-hub__remove"
                  onClick={() => setFriendToRemove(friend)}
                  aria-label={`解除與 ${friend.display_name} 的好友關係`}
                >
                  <IconUserX aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="friends-hub__empty">
            <IconUserPlus aria-hidden="true" />
            <p>還沒有好友，從好友碼開始找人吧。</p>
          </div>
        )}
        {friends.length > 3 ? (
          <button
            type="button"
            className="button button--ghost friends-hub__show-more"
            aria-controls="friends-list"
            aria-expanded={showAllFriends}
            onClick={() => setShowAllFriends((current) => !current)}
          >
            {showAllFriends ? "收合" : "查看更多"}
          </button>
        ) : null}
      </section>

      <section className="friends-hub__privacy" aria-labelledby="social-privacy-title">
        <div>
          <div className="friends-hub__privacy-heading">
            <IconShieldLock aria-hidden="true" />
            <h3 id="social-privacy-title">社交隱私</h3>
          </div>
          <p>關閉後，非好友不能傳送新的私聊；好友不受影響。</p>
        </div>
        <label className="friends-hub__switch">
          <span className="sr-only">接受陌生人第一則私訊</span>
          <input
            type="checkbox"
            checked={acceptStrangerMessages}
            onChange={(event) => void updatePrivacy(event.target.checked)}
            disabled={savingPrivacy}
          />
          <span aria-hidden="true" />
        </label>
      </section>

      {notice ? (
        <p className="friends-hub__notice" role="status">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="friends-hub__error" role="alert">
          {error}
        </p>
      ) : null}
      <AppConfirmDialog
        open={friendToRemove !== null}
        title="解除好友"
        message={friendToRemove ? `確定要解除與 ${friendToRemove.display_name} 的好友關係嗎？` : ""}
        confirmLabel="解除好友"
        danger
        onCancel={() => setFriendToRemove(null)}
        onConfirm={() => {
          if (friendToRemove) void unfriend(friendToRemove);
        }}
      />
    </section>
  );
}
