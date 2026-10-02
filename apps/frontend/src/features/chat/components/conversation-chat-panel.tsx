"use client";

import {
  IconArrowBackUp,
  IconArrowDown,
  IconArrowUp,
  IconDotsVertical,
  IconMessageCircle,
  IconPin,
  IconSend,
  IconX,
} from "@tabler/icons-react";
import { FormEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  type ChatMessage,
  fetchConversationMessages,
  fetchMealPinnedMessages,
  fetchMealMessages,
  fetchPinnedMessages,
} from "@/features/chat/api/chat-api";
import { ParticipantAvatarMenu } from "@/features/chat/components/participant-avatar-menu";
import { userApi } from "@/shared/auth/user-api";
import { mergeChatMessages, sortChatMessages } from "@/features/chat/utils/chat-order";
import { type RealtimeEvent, useRealtime } from "@/shared/realtime/realtime";

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

type MessageAction = "reply" | "recall" | "pin";

function MessageActions({
  message,
  active,
  onToggle,
  onAction,
}: {
  message: ChatMessage;
  active: boolean;
  onToggle: () => void;
  onAction: (action: MessageAction) => void;
}) {
  return (
    <div className="meal-chat__actions">
      <button
        type="button"
        className="meal-chat__more"
        aria-label={`更多操作：${message.sender.display_name}`}
        aria-expanded={active}
        aria-haspopup="menu"
        onClick={onToggle}
      >
        <IconDotsVertical aria-hidden="true" />
      </button>
      {active ? (
        <div className="meal-chat__action-menu" role="menu">
          <button type="button" role="menuitem" onClick={() => onAction("reply")}>
            <IconArrowBackUp aria-hidden="true" /> 回覆
          </button>
          {message.can_recall ? (
            <button type="button" role="menuitem" onClick={() => onAction("recall")}>
              <IconX aria-hidden="true" /> 收回
            </button>
          ) : null}
          <button type="button" role="menuitem" onClick={() => onAction("pin")}>
            <IconPin aria-hidden="true" /> {message.is_pinned ? "取消釘選" : "釘選"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

const BOTTOM_THRESHOLD = 72;

export type ConversationChatPanelProps = {
  conversationId?: string;
  mealId?: string;
  title?: string;
  ariaLabel?: string;
  placeholder?: string;
  emptyMessage?: string;
};

export function ConversationChatPanel({
  conversationId,
  mealId,
  title = "聊天室",
  ariaLabel = "聊天室",
  placeholder = "輸入訊息…",
  emptyMessage = "還沒有訊息，先打聲招呼吧。",
}: ConversationChatPanelProps) {
  const {
    recallMessage,
    pinMessage,
    sendConversationRead,
    sendDirectMessage,
    sendMealTyping,
    sendMessage,
    sendTyping,
    status,
    subscribe,
    subscribeConversation,
    unpinMessage,
  } = useRealtime();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);
  const [typingName, setTypingName] = useState<string | null>(null);
  const [readMessageId, setReadMessageId] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [replyingTo, setReplyingTo] = useState<ChatMessage | null>(null);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [pinnedMessages, setPinnedMessages] = useState<ChatMessage[]>([]);
  const [showPinned, setShowPinned] = useState(false);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const messageStateRef = useRef<ChatMessage[]>([]);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollModeRef = useRef<"bottom" | "older" | null>(null);
  const previousScrollHeightRef = useRef(0);
  const typingTimerRef = useRef<number | null>(null);
  const typingActiveRef = useRef(false);

  const currentConversationId = conversationId ?? messages[0]?.conversation_id;

  useEffect(() => {
    messageStateRef.current = messages;
  }, [messages]);

  useEffect(() => {
    let active = true;
    void userApi<{ id: string }>("/auth/me")
      .then((user) => {
        if (active) setCurrentUserId(user.id);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const markRead = useCallback(
    (messageId: string) => {
      if (!currentConversationId) return;
      void sendConversationRead(currentConversationId, messageId).catch(() => undefined);
    },
    [currentConversationId, sendConversationRead],
  );

  const loadPage = useCallback(
    (nextCursor?: string, signal?: AbortSignal) => {
      if (mealId) return fetchMealMessages(mealId, nextCursor, signal);
      if (conversationId) return fetchConversationMessages(conversationId, nextCursor, signal);
      return Promise.reject(new Error("conversation target required"));
    },
    [conversationId, mealId],
  );

  const loadPinned = useCallback(
    (signal?: AbortSignal) => {
      if (mealId) return fetchMealPinnedMessages(mealId, signal);
      if (conversationId) return fetchPinnedMessages(conversationId, signal);
      return Promise.reject(new Error("conversation target required"));
    },
    [conversationId, mealId],
  );

  const loadInitial = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const [page, pins] = await Promise.all([loadPage(undefined, signal), loadPinned(signal)]);
        scrollModeRef.current = "bottom";
        setMessages(sortChatMessages(page.messages));
        setPinnedMessages(sortChatMessages(pins.messages));
        setCursor(page.next_cursor);
        setUnreadCount(0);
        setState("ready");
        const newest = page.messages.at(-1);
        if (newest) {
          const targetConversationId = conversationId ?? newest.conversation_id;
          void sendConversationRead(targetConversationId, newest.id).catch(() => undefined);
        }
      } catch {
        if (!signal?.aborted) setState("error");
      }
    },
    [conversationId, loadPage, loadPinned, sendConversationRead],
  );

  useEffect(() => {
    const controller = new AbortController();
    const handleEvent = (event: RealtimeEvent) => {
      if (
        event.type === "message.created" ||
        event.type === "message.recalled" ||
        event.type === "message.pinned" ||
        event.type === "message.unpinned"
      ) {
        const element = messagesRef.current;
        const isNearBottom = element
          ? element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD
          : true;
        scrollModeRef.current = isNearBottom ? "bottom" : null;
        setMessages((current) => mergeChatMessages(current, [event.message]));
        if (event.type === "message.pinned") {
          setPinnedMessages((current) => mergeChatMessages(current, [event.message]));
        } else if (event.type === "message.unpinned") {
          setPinnedMessages((current) =>
            current.filter((message) => message.id !== event.message.id),
          );
        } else if (event.message.is_pinned) {
          setPinnedMessages((current) => mergeChatMessages(current, [event.message]));
        }
        if (!isNearBottom && event.type === "message.created") {
          setUnreadCount((current) => current + 1);
        }
        if (isNearBottom && event.type === "message.created") markRead(event.message.id);
      } else if (event.type === "conversation.read") {
        const readTarget = messageStateRef.current.find(
          (message) => message.id === event.message_id,
        );
        if (readTarget?.sender.user_id === event.user_id) return;
        if (!currentUserId || event.user_id !== currentUserId) {
          setReadMessageId(event.message_id);
        }
      } else if (event.type === "typing.updated") {
        setTypingName(event.is_typing ? event.display_name : null);
      }
    };
    const unsubscribe = mealId
      ? subscribe("chat", mealId, handleEvent)
      : conversationId
        ? subscribeConversation(conversationId, handleEvent)
        : () => undefined;
    const initialTimer = window.setTimeout(() => void loadInitial(controller.signal), 0);
    return () => {
      window.clearTimeout(initialTimer);
      controller.abort();
      unsubscribe();
    };
  }, [
    conversationId,
    currentUserId,
    loadInitial,
    markRead,
    mealId,
    subscribe,
    subscribeConversation,
  ]);

  useLayoutEffect(() => {
    const element = messagesRef.current;
    if (!element || scrollModeRef.current === null) return;
    if (scrollModeRef.current === "older") {
      element.scrollTop += element.scrollHeight - previousScrollHeightRef.current;
    } else {
      element.scrollTop = element.scrollHeight;
    }
    scrollModeRef.current = null;
  }, [messages]);

  const handleScroll = () => {
    const element = messagesRef.current;
    if (!element) return;
    const isNearBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD;
    if (isNearBottom) {
      setUnreadCount(0);
      const newest = messages.at(-1);
      if (newest) markRead(newest.id);
    }
  };

  const loadOlder = async () => {
    if (!cursor || !messagesRef.current) return;
    previousScrollHeightRef.current = messagesRef.current.scrollHeight;
    try {
      const page = await loadPage(cursor);
      scrollModeRef.current = "older";
      setMessages((current) => mergeChatMessages(current, page.messages));
      setCursor(page.next_cursor);
    } catch {
      setError("較早的訊息暫時無法載入，請再試一次。");
    }
  };

  const jumpToBottom = () => {
    scrollModeRef.current = "bottom";
    setUnreadCount(0);
    const newest = messages.at(-1);
    if (newest) markRead(newest.id);
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  };

  const setTyping = (value: string) => {
    const target = conversationId ?? mealId;
    if (!target) return;
    if (typingTimerRef.current !== null) window.clearTimeout(typingTimerRef.current);
    const isTyping = Boolean(value.trim());
    if (isTyping && !typingActiveRef.current) {
      typingActiveRef.current = true;
      if (conversationId) sendTyping(target, true);
      else sendMealTyping(target, true);
    }
    if (!isTyping && typingActiveRef.current) {
      typingActiveRef.current = false;
      if (conversationId) sendTyping(target, false);
      else sendMealTyping(target, false);
      return;
    }
    if (isTyping) {
      typingTimerRef.current = window.setTimeout(() => {
        typingActiveRef.current = false;
        if (conversationId) sendTyping(target, false);
        else sendMealTyping(target, false);
      }, 900);
    }
  };

  useEffect(
    () => () => {
      if (typingTimerRef.current !== null) window.clearTimeout(typingTimerRef.current);
      if (typingActiveRef.current) {
        const target = conversationId ?? mealId;
        if (target) {
          if (conversationId) sendTyping(target, false);
          else sendMealTyping(target, false);
        }
      }
    },
    [conversationId, mealId, sendMealTyping, sendTyping],
  );

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = content.trim();
    if (!message || sending) return;
    setSending(true);
    setError("");
    try {
      if (mealId) await sendMessage(mealId, message, replyingTo?.id);
      else if (conversationId) {
        await sendDirectMessage(conversationId, message, replyingTo?.id);
      }
      setContent("");
      setReplyingTo(null);
      setTyping("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "訊息傳送失敗，請再試一次。");
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (!activeMenuId) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActiveMenuId(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [activeMenuId]);

  const handleMessageAction = async (message: ChatMessage, action: "reply" | "recall" | "pin") => {
    setActiveMenuId(null);
    if (action === "reply") {
      setReplyingTo(message);
      window.requestAnimationFrame(() => composerRef.current?.focus());
      return;
    }
    if (!currentConversationId) return;
    try {
      if (action === "recall") {
        await recallMessage(currentConversationId, message.id);
      } else if (message.is_pinned) {
        await unpinMessage(currentConversationId, message.id);
      } else {
        await pinMessage(currentConversationId, message.id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "聊天室操作失敗，請再試一次。");
    }
  };

  const isOwnMessage = (message: ChatMessage) =>
    currentUserId ? message.sender.user_id === currentUserId : Boolean(message.is_mine);

  return (
    <section className="meal-chat" aria-label={ariaLabel}>
      <header className="meal-chat__header">
        <div>
          <IconMessageCircle aria-hidden="true" />
          <span>
            <strong>{title}</strong>
            <small>{status === "connected" ? "即時連線中" : "正在重新連線"}</small>
          </span>
        </div>
        <i className={status === "connected" ? "is-online" : ""} aria-hidden="true" />
      </header>

      <div
        className="meal-chat__messages"
        ref={messagesRef}
        onScroll={handleScroll}
        aria-live="polite"
      >
        {cursor ? (
          <button type="button" className="meal-chat__older" onClick={() => void loadOlder()}>
            <IconArrowUp aria-hidden="true" /> 載入較早訊息
          </button>
        ) : null}
        {pinnedMessages.length > 0 ? (
          <div className="meal-chat__pinned-bar">
            <button type="button" onClick={() => setShowPinned((current) => !current)}>
              <IconPin aria-hidden="true" />
              {pinnedMessages.length} 則釘選訊息
            </button>
            {showPinned ? (
              <div className="meal-chat__pinned-list" role="list">
                {pinnedMessages.map((message) => (
                  <button
                    type="button"
                    role="listitem"
                    key={message.id}
                    onClick={() => {
                      setShowPinned(false);
                      messagesRef.current
                        ?.querySelector<HTMLElement>(`[data-message-id="${message.id}"]`)
                        ?.scrollIntoView({ behavior: "smooth", block: "center" });
                    }}
                  >
                    <strong>{message.sender.display_name}</strong>
                    <span>{message.is_recalled ? "訊息已收回" : message.content}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {state === "loading" ? <p className="meal-chat__state">正在載入聊天紀錄…</p> : null}
        {state === "error" ? (
          <div className="meal-chat__state">
            <p>聊天紀錄暫時無法載入。</p>
            <button
              type="button"
              onClick={() => {
                setState("loading");
                void loadInitial();
              }}
            >
              重試
            </button>
          </div>
        ) : null}
        {state === "ready" && messages.length === 0 ? (
          <p className="meal-chat__state">{emptyMessage}</p>
        ) : null}
        {messages.map((message) => {
          const isMine = isOwnMessage(message);
          return (
            <article
              className={`meal-chat__message ${isMine ? "is-mine" : "is-theirs"}`}
              data-message-id={message.id}
              key={message.id}
            >
              {!isMine ? (
                <ParticipantAvatarMenu
                  userId={message.sender.user_id}
                  displayName={message.sender.display_name}
                  avatarUrl={message.sender.avatar_url}
                  className="meal-chat__avatar"
                />
              ) : null}
              <div className="meal-chat__message-content">
                <header>
                  {!isMine ? <strong>{message.sender.display_name}</strong> : null}
                  <time dateTime={message.created_at}>{formatMessageTime(message.created_at)}</time>
                </header>
                <div className="meal-chat__message-row">
                  <MessageActions
                    message={message}
                    active={activeMenuId === message.id}
                    onToggle={() =>
                      setActiveMenuId((current) => (current === message.id ? null : message.id))
                    }
                    onAction={(action) => void handleMessageAction(message, action)}
                  />
                  <div className="meal-chat__bubble">
                    {message.reply_to ? (
                      <button
                        type="button"
                        className="meal-chat__reply-preview"
                        onClick={() => {
                          messagesRef.current
                            ?.querySelector<HTMLElement>(
                              `[data-message-id="${message.reply_to?.id}"]`,
                            )
                            ?.scrollIntoView({ behavior: "smooth", block: "center" });
                        }}
                      >
                        <strong>回覆 {message.reply_to.sender.display_name}</strong>
                        <span>
                          {message.reply_to.is_recalled
                            ? "訊息已收回"
                            : message.reply_to.content || "（空白訊息）"}
                        </span>
                      </button>
                    ) : null}
                    <p className={message.is_recalled ? "is-recalled" : ""}>
                      {message.is_recalled ? "訊息已收回" : message.content}
                    </p>
                  </div>
                </div>
                {isMine && readMessageId === message.id ? (
                  <small className="meal-chat__read-state">已讀</small>
                ) : null}
                {message.is_pinned ? (
                  <small className="meal-chat__pin-state">
                    <IconPin aria-hidden="true" /> 已釘選
                  </small>
                ) : null}
              </div>
            </article>
          );
        })}
        {unreadCount > 0 ? (
          <button type="button" className="meal-chat__new-messages" onClick={jumpToBottom}>
            <IconArrowDown aria-hidden="true" /> {unreadCount} 則新訊息
          </button>
        ) : null}
        {typingName ? <p className="meal-chat__typing">{typingName} 正在輸入…</p> : null}
      </div>

      <form className="meal-chat__composer" onSubmit={(event) => void submit(event)}>
        <label htmlFor={`conversation-chat-${conversationId ?? mealId}`}>傳送訊息</label>
        {replyingTo ? (
          <div className="meal-chat__replying-to">
            <div>
              <strong>回覆 {replyingTo.sender.display_name}</strong>
              <span>{replyingTo.is_recalled ? "訊息已收回" : replyingTo.content}</span>
            </div>
            <button type="button" onClick={() => setReplyingTo(null)} aria-label="取消回覆">
              <IconX aria-hidden="true" />
            </button>
          </div>
        ) : null}
        <textarea
          ref={composerRef}
          id={`conversation-chat-${conversationId ?? mealId}`}
          value={content}
          maxLength={2000}
          rows={2}
          placeholder={placeholder}
          onChange={(event) => {
            setContent(event.target.value);
            setTyping(event.target.value);
          }}
        />
        <button
          type="submit"
          className="button button--primary"
          disabled={sending || status !== "connected" || !content.trim()}
        >
          <IconSend aria-hidden="true" />
          {sending ? "傳送中" : "傳送"}
        </button>
      </form>
      {error ? (
        <p className="meal-chat__error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
