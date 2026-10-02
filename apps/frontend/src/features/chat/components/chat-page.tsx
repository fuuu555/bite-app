"use client";

import { IconArrowLeft, IconMessageCircle, IconUserPlus, IconUsers } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  fetchDirectConversations,
  fetchMealConversations,
  type ConversationSummary,
} from "@/features/chat/api/chat-api";
import { ConversationChatPanel } from "@/features/chat/components/conversation-chat-panel";
import { FriendsHubPanel } from "@/features/profile/components/friends-hub-panel";
import { MyProfile, userApi } from "@/shared/auth/user-api";
import { useRealtime } from "@/shared/realtime/realtime";

type ChatCategory = "chat" | "meal" | "friends";

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
  const [category, setCategory] = useState<ChatCategory>(
    requestedCategory === "friends" || requestedCategory === "meal" ? requestedCategory : "chat",
  );
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [profileState, setProfileState] = useState<"loading" | "ready" | "error">("loading");
  const [socialNotice, setSocialNotice] = useState("");

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
        if (event.type === "social.updated" && event.action === "friend_removed") {
          setSocialNotice("你們已解除好友。聊天紀錄仍會保留，後續私聊依對方設定而定。");
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
  }, [category, load, subscribe]);

  useEffect(() => {
    if (!socialNotice) return;
    const timer = window.setTimeout(() => setSocialNotice(""), 8_000);
    return () => window.clearTimeout(timer);
  }, [socialNotice]);

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
    if (requestedCategory === "direct") {
      router.replace("/chat?category=chat");
      return;
    }
    if (
      requestedCategory !== "chat" &&
      requestedCategory !== "friends" &&
      requestedCategory !== "meal"
    ) {
      router.replace("/chat?category=chat");
    }
  }, [requestedCategory, router]);

  const selectCategory = (nextCategory: ChatCategory) => {
    setCategory(nextCategory);
    router.replace(`/chat?category=${nextCategory}`);
  };

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

      {socialNotice ? (
        <p className="chat-page__social-notice" role="status">
          {socialNotice}
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

      {selectedConversation && category === "chat" ? (
        <section className="chat-page__selected">
          <button
            type="button"
            className="back-link"
            onClick={() => router.replace(`/chat?category=${category}`)}
          >
            <IconArrowLeft aria-hidden="true" /> 返回聊天列表
          </button>
          <ConversationChatPanel
            conversationId={selectedConversation.conversation_id}
            title={selectedConversation.other_user?.display_name ?? "聊天室"}
            ariaLabel="聊天室"
            placeholder="輸入訊息…"
          />
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
            <section className="chat-list" aria-label="聊天室列表">
              {conversations.map((conversation) => (
                <Link
                  href={
                    category === "meal"
                      ? `/meals/${conversation.meal_id}#chat`
                      : `/chat?category=chat&conversation=${conversation.conversation_id}`
                  }
                  key={conversation.conversation_id}
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
              ))}
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
