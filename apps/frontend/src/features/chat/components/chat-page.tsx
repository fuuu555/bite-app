"use client";

import {
  IconArrowLeft,
  IconMessageCircle,
  IconTrash,
  IconUserPlus,
  IconUsers,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ChatApiError,
  deleteConversation,
  fetchDirectConversations,
  fetchMealConversations,
  type ConversationSummary,
} from "@/features/chat/api/chat-api";
import { ConversationChatPanel } from "@/features/chat/components/conversation-chat-panel";
import { resolveChatCategory, type ChatCategory } from "@/features/chat/utils/chat-navigation";
import { unblockUser } from "@/features/profile/api/social-api";
import { FriendsHubPanel } from "@/features/profile/components/friends-hub-panel";
import { MyProfile, userApi } from "@/shared/auth/user-api";
import { useRealtime } from "@/shared/realtime/realtime";
import {
  clearPendingFriendRemoved,
  hasPendingFriendRemoved,
} from "@/shared/realtime/social-notice-storage";
import { AppConfirmDialog } from "@/shared/ui/app-confirm-dialog";

type SocialNoticeAction = "friend_removed" | "user_blocked" | "blocked_by_user";
type SocialNotice = { action: SocialNoticeAction; conversationId: string };

function ChatRelationshipNotice({
  action,
  onContinue,
  onUnblock,
  onBack,
  pending,
}: {
  action: SocialNoticeAction;
  onContinue: () => void;
  onUnblock: () => void;
  onBack: () => void;
  pending: boolean;
}) {
  const copy = {
    friend_removed: {
      title: "你們已不是好友",
      message: "聊天紀錄仍會保留，要繼續聊天嗎？",
      accent: "chat-relationship-notice--neutral",
    },
    user_blocked: {
      title: "你已封鎖此使用者",
      message: "目前無法繼續私聊；解除封鎖後才能恢復。",
      accent: "chat-relationship-notice--danger",
    },
    blocked_by_user: {
      title: "目前無法繼續聊天",
      message: "你目前無法與此使用者私聊。",
      accent: "chat-relationship-notice--danger",
    },
  }[action];

  return (
    <section className={`chat-relationship-notice ${copy.accent}`} role="status">
      <p className="chat-relationship-notice__eyebrow">聊天狀態</p>
      <h2>{copy.title}</h2>
      <p>{copy.message}</p>
      <div className="chat-relationship-notice__actions">
        {action === "friend_removed" ? (
          <button type="button" className="button button--primary" onClick={onContinue}>
            繼續聊天
          </button>
        ) : null}
        {action === "user_blocked" ? (
          <button
            type="button"
            className="button button--primary"
            onClick={onUnblock}
            disabled={pending}
          >
            {pending ? "處理中…" : "解除封鎖"}
          </button>
        ) : null}
        <button type="button" className="button button--ghost" onClick={onBack}>
          返回列表
        </button>
      </div>
    </section>
  );
}

function formatLatestTime(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { subscribe } = useRealtime();
  const requestedCategory = searchParams.get("category");
  const category = resolveChatCategory(requestedCategory);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [profileState, setProfileState] = useState<"loading" | "ready" | "error">("loading");
  const [socialNotice, setSocialNotice] = useState<SocialNotice | null>(null);
  const [dismissedFriendRemovalId, setDismissedFriendRemovalId] = useState<string | null>(null);
  const [socialActionPending, setSocialActionPending] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteFeedback, setDeleteFeedback] = useState("");
  const deleteFeedbackTimerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (deleteFeedbackTimerRef.current !== null) {
        window.clearTimeout(deleteFeedbackTimerRef.current);
      }
    },
    [],
  );

  const selectedConversationId = searchParams.get("conversation");
  const selectedConversation = conversations.find(
    (conversation) => conversation.conversation_id === selectedConversationId,
  );

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        if (category === "friends") {
          setConversations([]);
          return;
        }
        const response =
          category === "meal"
            ? await fetchMealConversations(signal)
            : await Promise.all([
                fetchDirectConversations("direct", signal),
                fetchDirectConversations("friends", signal),
              ]);
        const loadedConversations = Array.isArray(response)
          ? response.flatMap((item) => item.conversations)
          : response.conversations;
        loadedConversations.sort((left, right) => {
          const leftTime = left.latest_message?.created_at ?? "";
          const rightTime = right.latest_message?.created_at ?? "";
          return rightTime.localeCompare(leftTime);
        });
        setConversations(loadedConversations);
        setState("ready");
      } catch {
        if (!signal?.aborted) setState("error");
      }
    },
    [category],
  );

  useEffect(() => {
    const controller = new AbortController();
    const unsubscribeList = subscribe(
      category === "meal" ? "meal-list" : "conversation-list",
      undefined,
      (event) => {
        const conversationId = event.type === "social.updated" ? event.conversation_id : null;
        if (event.type === "social.updated") {
          if (
            conversationId &&
            (event.action === "friend_removed" || event.action === "friend_created")
          ) {
            setDismissedFriendRemovalId((current) => (current === conversationId ? null : current));
          }
          if (conversationId && conversationId === selectedConversationId) {
            if (event.action === "friend_created") {
              setSocialNotice(null);
            } else if (event.action) {
              setSocialNotice({ action: event.action, conversationId });
            }
          }
          void load();
          return;
        }
        if (
          event.type === "conversation.deleted" &&
          event.conversation_id === selectedConversationId
        ) {
          setSocialNotice(null);
          router.replace(`/chat?category=${category}`);
        }
        void load();
      },
    );
    const initialTimer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(initialTimer);
      controller.abort();
      unsubscribeList();
    };
  }, [category, load, router, selectedConversationId, subscribe]);

  useEffect(() => {
    if (category !== "friends") return;
    const controller = new AbortController();
    const initialTimer = window.setTimeout(() => {
      void userApi<MyProfile>("/me/profile", { signal: controller.signal })
        .then((loadedProfile) => {
          setProfile(loadedProfile);
          setProfileState("ready");
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setProfileState("error");
        });
    }, 0);
    return () => {
      window.clearTimeout(initialTimer);
      controller.abort();
    };
  }, [category]);

  useEffect(() => {
    const nextCategory = resolveChatCategory(requestedCategory);
    if (requestedCategory !== nextCategory) {
      const nextParams = new URLSearchParams(searchParams.toString());
      nextParams.set("category", nextCategory);
      router.replace(`/chat?${nextParams.toString()}`);
    }
  }, [requestedCategory, router, searchParams]);

  const selectCategory = (nextCategory: ChatCategory) => {
    if (deleteFeedbackTimerRef.current !== null) {
      window.clearTimeout(deleteFeedbackTimerRef.current);
      deleteFeedbackTimerRef.current = null;
    }
    setDeleteFeedback("");
    router.replace(`/chat?category=${nextCategory}`);
  };

  const requestedNotice = searchParams.get("notice");
  const requestedNoticeUserId = searchParams.get("user");
  const routeBlockedNotice =
    category === "chat" && requestedNotice === "blocked" && selectedConversationId
      ? { action: "user_blocked" as const, conversationId: selectedConversationId }
      : null;
  const storedFriendRemovedNotice =
    category === "chat" &&
    selectedConversationId &&
    dismissedFriendRemovalId !== selectedConversationId &&
    hasPendingFriendRemoved(selectedConversationId)
      ? { action: "friend_removed" as const, conversationId: selectedConversationId }
      : null;
  const activeSocialNotice =
    (socialNotice?.conversationId === selectedConversationId ? socialNotice : routeBlockedNotice) ??
    storedFriendRemovedNotice;
  const selectedTitle = selectedConversation?.other_user?.display_name ?? "聊天室";
  const chatTargetUserId = selectedConversation?.other_user?.user_id ?? requestedNoticeUserId;
  const hasSelectedChat =
    category === "chat" && Boolean(selectedConversation || routeBlockedNotice);

  function clearNoticeAndReturnToList() {
    router.replace(`/chat?category=${category}`);
  }

  function continueAfterFriendRemoved() {
    if (selectedConversationId) {
      clearPendingFriendRemoved(selectedConversationId);
      setDismissedFriendRemovalId(selectedConversationId);
    }
    setSocialNotice(null);
  }

  async function unblockChatPartner() {
    if (!chatTargetUserId) return;
    setSocialActionPending(true);
    try {
      await unblockUser(chatTargetUserId);
      setSocialNotice(null);
      router.replace(`/chat?category=chat&conversation=${selectedConversationId}`);
      await load();
    } catch {
      // The existing chat panel/API error state remains the source of truth if this fails.
    } finally {
      setSocialActionPending(false);
    }
  }

  function openDeleteDialog(conversation: ConversationSummary) {
    if (deleteFeedbackTimerRef.current !== null) {
      window.clearTimeout(deleteFeedbackTimerRef.current);
      deleteFeedbackTimerRef.current = null;
    }
    setDeleteFeedback("");
    setDeleteTarget(conversation);
  }

  function showDeleteSuccess() {
    if (deleteFeedbackTimerRef.current !== null) {
      window.clearTimeout(deleteFeedbackTimerRef.current);
    }
    setDeleteFeedback("聊天室已刪除，雙方聊天紀錄已永久清除。");
    deleteFeedbackTimerRef.current = window.setTimeout(() => {
      setDeleteFeedback("");
      deleteFeedbackTimerRef.current = null;
    }, 2000);
  }

  async function confirmDeleteConversation() {
    if (!deleteTarget || deletePending) return;
    const conversationId = deleteTarget.conversation_id;
    setDeletePending(true);
    setDeleteFeedback("");
    try {
      await deleteConversation(conversationId);
      setDeleteTarget(null);
      showDeleteSuccess();
      if (selectedConversationId === conversationId) {
        router.replace(`/chat?category=${category}`);
      }
      await load();
    } catch (error) {
      setDeleteFeedback(
        error instanceof ChatApiError && typeof error.detail === "string"
          ? error.detail
          : "刪除聊天室失敗，請稍後再試。",
      );
    } finally {
      setDeletePending(false);
    }
  }

  const renderConversationRows = (items: ConversationSummary[]) =>
    items.map((conversation) => (
      <div className="chat-list__row" key={conversation.conversation_id}>
        <Link
          className="chat-list__link"
          href={
            category === "meal"
              ? `/meals/${conversation.meal_id}#chat`
              : `/chat?category=chat&conversation=${conversation.conversation_id}`
          }
        >
          <span className="chat-list__icon">
            <IconMessageCircle aria-hidden="true" />
          </span>
          <span className="chat-list__content">
            <strong>
              {category === "meal"
                ? conversation.meal_title
                : (conversation.other_user?.display_name ?? "聊天室")}
            </strong>
            <small>
              {conversation.latest_message
                ? `${conversation.latest_message.sender.display_name}：${conversation.latest_message.content}`
                : "聊天室已開放，來打聲招呼吧。"}
            </small>
          </span>
          {conversation.latest_message ? (
            <time dateTime={conversation.latest_message.created_at}>
              {formatLatestTime(conversation.latest_message.created_at)}
            </time>
          ) : null}
        </Link>
        {conversation.kind === "direct" ? (
          <button
            type="button"
            className="chat-list__delete"
            aria-label={`刪除與${conversation.other_user?.display_name ?? "對方"}的聊天室`}
            onClick={() => openDeleteDialog(conversation)}
          >
            <IconTrash aria-hidden="true" />
          </button>
        ) : null}
      </div>
    ));

  return (
    <main className="chat-page">
      <header className="chat-page__header">
        <p>BITETALK</p>
        <h1>聊天室</h1>
      </header>
      <nav className="chat-tabs" aria-label="聊天室分類">
        <button
          type="button"
          className={category === "chat" ? "is-active" : ""}
          onClick={() => selectCategory("chat")}
        >
          聊天
        </button>
        <button
          type="button"
          className={category === "meal" ? "is-active" : ""}
          onClick={() => selectCategory("meal")}
        >
          約飯聊天室
        </button>
        <button
          type="button"
          className={category === "friends" ? "is-active" : ""}
          onClick={() => selectCategory("friends")}
        >
          好友管理
        </button>
      </nav>
      {deleteFeedback ? (
        <p className="chat-page__feedback" role="status">
          {deleteFeedback}
        </p>
      ) : null}

      {category === "friends" ? (
        profileState === "loading" ? (
          <p className="chat-page__state">正在載入好友管理…</p>
        ) : null
      ) : null}
      {category === "friends" && profileState === "error" ? (
        <section className="chat-page__state">
          <IconUserPlus aria-hidden="true" />
          <p>好友管理暫時無法載入。</p>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => router.refresh()}
          >
            重試
          </button>
        </section>
      ) : null}
      {category === "friends" && profileState === "ready" && profile ? (
        <FriendsHubPanel profile={profile} />
      ) : null}

      {hasSelectedChat ? (
        <section className="chat-page__selected">
          <div className="chat-page__selected-toolbar">
            <button
              type="button"
              className="back-link"
              onClick={() => router.replace(`/chat?category=${category}`)}
            >
              <IconArrowLeft aria-hidden="true" /> 返回聊天列表
            </button>
            {selectedConversation?.kind === "direct" ? (
              <button
                type="button"
                className="button button--ghost chat-page__delete-button"
                onClick={() => openDeleteDialog(selectedConversation)}
              >
                <IconTrash aria-hidden="true" /> 刪除聊天室
              </button>
            ) : null}
          </div>
          {activeSocialNotice?.action === "user_blocked" ||
          activeSocialNotice?.action === "blocked_by_user" ? (
            <ChatRelationshipNotice
              action={activeSocialNotice.action}
              onContinue={() => setSocialNotice(null)}
              onUnblock={() => void unblockChatPartner()}
              onBack={clearNoticeAndReturnToList}
              pending={socialActionPending}
            />
          ) : (
            <>
              {activeSocialNotice?.action === "friend_removed" ? (
                <ChatRelationshipNotice
                  action={activeSocialNotice.action}
                  onContinue={continueAfterFriendRemoved}
                  onUnblock={() => undefined}
                  onBack={clearNoticeAndReturnToList}
                  pending={false}
                />
              ) : null}
              <ConversationChatPanel
                conversationId={selectedConversation?.conversation_id}
                title={selectedTitle}
                ariaLabel="聊天室"
                placeholder="輸入訊息…"
              />
            </>
          )}
        </section>
      ) : null}

      {!selectedConversation && category !== "friends" ? (
        <>
          {state === "loading" ? <p className="chat-page__state">正在載入聊天室…</p> : null}
          {state === "error" ? (
            <section className="chat-page__state">
              <p>聊天室列表暫時無法載入。</p>
              <button
                type="button"
                className="button button--secondary"
                onClick={() => void load()}
              >
                重試
              </button>
            </section>
          ) : null}
          {state === "ready" && conversations.length === 0 ? (
            <section className="chat-page__empty">
              <IconUsers aria-hidden="true" />
              <h2>{category === "meal" ? "還沒有可進入的飯局聊天室" : "還沒有一對一聊天"}</h2>
              <p>
                {category === "meal"
                  ? "正式加入約飯後，聊天室會出現在這裡。"
                  : "從其他使用者的公開個人頁面或好友管理開始聊天吧。"}
              </p>
              <Link className="button button--primary" href={category === "meal" ? "/meals" : "/"}>
                {category === "meal" ? "查看約飯" : "去探索"}
              </Link>
            </section>
          ) : null}
          {state === "ready" && conversations.length > 0 ? (
            category === "meal" ? (
              <section className="chat-list" aria-label="約飯聊天室列表">
                {renderConversationRows(conversations)}
              </section>
            ) : (
              <div className="chat-list-groups">
                {conversations.some((conversation) => conversation.category === "friends") ? (
                  <section className="chat-list-group" aria-labelledby="friend-chats-title">
                    <h2 id="friend-chats-title">好友聊天</h2>
                    <section className="chat-list" aria-label="好友聊天列表">
                      {renderConversationRows(
                        conversations.filter((conversation) => conversation.category === "friends"),
                      )}
                    </section>
                  </section>
                ) : null}
                {conversations.some((conversation) => conversation.category === "direct") ? (
                  <section className="chat-list-group" aria-labelledby="direct-chats-title">
                    <h2 id="direct-chats-title">私聊</h2>
                    <section className="chat-list" aria-label="私聊列表">
                      {renderConversationRows(
                        conversations.filter((conversation) => conversation.category === "direct"),
                      )}
                    </section>
                  </section>
                ) : null}
              </div>
            )
          ) : null}
        </>
      ) : null}
      <AppConfirmDialog
        open={deleteTarget !== null}
        title="永久刪除聊天室？"
        message={`刪除後，你和${deleteTarget?.other_user?.display_name ?? "對方"}的所有聊天紀錄、回覆、釘選與已讀資料都會永久刪除，且無法恢復。`}
        confirmLabel={deletePending ? "刪除中…" : "永久刪除"}
        danger
        onCancel={() => {
          if (!deletePending) setDeleteTarget(null);
        }}
        onConfirm={() => void confirmDeleteConversation()}
      />
    </main>
  );
}
