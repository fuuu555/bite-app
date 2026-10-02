"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { clearPendingFriendRemoved, rememberFriendRemoved } from "./social-notice-storage";

export type RealtimeStatus = "connecting" | "connected" | "disconnected";
export type RealtimeChannel = "meal-list" | "conversation-list" | "state" | "chat";

export type MealUpdatedEvent = { type: "meal.updated"; meal_id: string };
export type MealListUpdatedEvent = { type: "meal.list.updated" };
export type ChatMessageReply = {
  id: string;
  sender: { user_id: string; display_name: string; avatar_url: string | null };
  content: string;
  is_recalled: boolean;
};
export type ChatMessage = {
  id: string;
  conversation_id: string;
  conversation_kind: "meal" | "direct";
  meal_id: string | null;
  sender: { user_id: string; display_name: string; avatar_url: string | null };
  content: string;
  created_at: string;
  is_recalled?: boolean;
  recalled_at?: string | null;
  can_recall?: boolean;
  is_mine?: boolean;
  reply_to?: ChatMessageReply | null;
  is_pinned?: boolean;
  pinned_at?: string | null;
  can_pin?: boolean;
};
export type MessageCreatedEvent = {
  type: "message.created";
  meal_id?: string;
  conversation_id: string;
  message: ChatMessage;
};
export type MessageRecalledEvent = {
  type: "message.recalled";
  conversation_id: string;
  meal_id?: string | null;
  message: MessageCreatedEvent["message"];
};
export type MessagePinnedEvent = {
  type: "message.pinned" | "message.unpinned";
  conversation_id: string;
  meal_id?: string | null;
  message: ChatMessage;
};
export type ConversationReadEvent = {
  type: "conversation.read";
  conversation_id: string;
  meal_id?: string | null;
  message_id: string;
  read_at: string;
  user_id: string;
};
export type TypingUpdatedEvent = {
  type: "typing.updated";
  conversation_id: string;
  meal_id?: string | null;
  user_id: string;
  display_name: string;
  is_typing: boolean;
};
export type ConversationUpdatedEvent = {
  type: "conversation.updated";
  conversation_id: string;
};
export type ConversationDeletedEvent = {
  type: "conversation.deleted";
  conversation_id: string;
};
export type SocialUpdatedEvent = {
  type: "social.updated";
  action?: "friend_created" | "friend_removed" | "user_blocked" | "blocked_by_user";
  conversation_id?: string | null;
};
export type RealtimeEvent =
  | MealUpdatedEvent
  | MealListUpdatedEvent
  | MessageCreatedEvent
  | MessageRecalledEvent
  | MessagePinnedEvent
  | ConversationReadEvent
  | TypingUpdatedEvent
  | ConversationUpdatedEvent
  | ConversationDeletedEvent
  | SocialUpdatedEvent;

type Subscription = {
  channel: RealtimeChannel;
  mealId?: string;
  conversationId?: string;
  listeners: Set<(event: RealtimeEvent) => void>;
};

type PendingRequest = {
  resolve: (messageId: string) => void;
  reject: (error: Error) => void;
  timer: number;
};

type RealtimeContextValue = {
  status: RealtimeStatus;
  subscribe: (
    channel: RealtimeChannel,
    mealId: string | undefined,
    listener: (event: RealtimeEvent) => void,
  ) => () => void;
  subscribeConversation: (
    conversationId: string,
    listener: (event: RealtimeEvent) => void,
  ) => () => void;
  sendMessage: (
    mealId: string,
    content: string,
    replyToMessageId?: string | null,
  ) => Promise<string>;
  sendDirectMessage: (
    conversationId: string,
    content: string,
    replyToMessageId?: string | null,
  ) => Promise<string>;
  sendConversationRead: (conversationId: string, messageId: string) => Promise<string>;
  sendTyping: (conversationId: string, isTyping: boolean) => void;
  sendMealTyping: (mealId: string, isTyping: boolean) => void;
  recallMessage: (conversationId: string, messageId: string) => Promise<string>;
  pinMessage: (conversationId: string, messageId: string) => Promise<string>;
  unpinMessage: (conversationId: string, messageId: string) => Promise<string>;
};

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export function resolveWebSocketUrl(currentUrl: string, configuredUrl?: string) {
  if (configuredUrl) return configuredUrl;
  const url = new URL("/api/v1/ws", currentUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function subscriptionKey(channel: RealtimeChannel, mealId?: string, conversationId?: string) {
  return `${channel}:${mealId ? `meal:${mealId}` : conversationId ? `conversation:${conversationId}` : ""}`;
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const socketRef = useRef<WebSocket | null>(null);
  const readyRef = useRef(false);
  const subscriptionsRef = useRef(new Map<string, Subscription>());
  const pendingRef = useRef(new Map<string, PendingRequest>());

  const sendSubscription = useCallback(
    (subscription: Subscription, action: "subscribe" | "unsubscribe") => {
      const socket = socketRef.current;
      if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(
        JSON.stringify({
          type: action,
          request_id: crypto.randomUUID(),
          channel: subscription.channel,
          ...(subscription.mealId ? { meal_id: subscription.mealId } : {}),
          ...(subscription.conversationId ? { conversation_id: subscription.conversationId } : {}),
        }),
      );
    },
    [],
  );

  useEffect(() => {
    let disposed = false;
    let reconnectTimer: number | null = null;
    let heartbeatTimer: number | null = null;
    let attempt = 0;

    const rejectPending = () => {
      for (const pending of pendingRef.current.values()) {
        window.clearTimeout(pending.timer);
        pending.reject(new Error("即時連線已中斷，請重新送出。"));
      }
      pendingRef.current.clear();
    };

    const connect = () => {
      if (disposed) return;
      setStatus(attempt === 0 ? "connecting" : "disconnected");
      const url = resolveWebSocketUrl(window.location.href, process.env.NEXT_PUBLIC_WS_URL);
      const socket = new WebSocket(url);
      socketRef.current = socket;
      readyRef.current = false;

      socket.addEventListener("message", (messageEvent) => {
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(String(messageEvent.data)) as Record<string, unknown>;
        } catch {
          return;
        }
        if (event.type === "ready") {
          readyRef.current = true;
          attempt = 0;
          setStatus("connected");
          for (const subscription of subscriptionsRef.current.values()) {
            sendSubscription(subscription, "subscribe");
          }
          if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer);
          heartbeatTimer = window.setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: "ping", request_id: crypto.randomUUID() }));
            }
          }, 25_000);
          return;
        }
        const requestId = typeof event.request_id === "string" ? event.request_id : null;
        if (event.type === "ack" && requestId) {
          const pending = pendingRef.current.get(requestId);
          if (pending) {
            window.clearTimeout(pending.timer);
            pendingRef.current.delete(requestId);
            pending.resolve(typeof event.message_id === "string" ? event.message_id : "");
          }
          return;
        }
        if (event.type === "error" && requestId) {
          const pending = pendingRef.current.get(requestId);
          if (pending) {
            window.clearTimeout(pending.timer);
            pendingRef.current.delete(requestId);
            pending.reject(
              new Error(typeof event.message === "string" ? event.message : "即時操作失敗"),
            );
          }
          return;
        }
        if (
          event.type !== "meal.updated" &&
          event.type !== "meal.list.updated" &&
          event.type !== "message.created" &&
          event.type !== "message.recalled" &&
          event.type !== "message.pinned" &&
          event.type !== "message.unpinned" &&
          event.type !== "conversation.read" &&
          event.type !== "typing.updated" &&
          event.type !== "conversation.updated" &&
          event.type !== "conversation.deleted" &&
          event.type !== "social.updated"
        ) {
          return;
        }
        const typedEvent = event as RealtimeEvent;
        if (typedEvent.type === "social.updated" && typedEvent.conversation_id) {
          if (typedEvent.action === "friend_removed") {
            rememberFriendRemoved(typedEvent.conversation_id);
          } else if (typedEvent.action === "friend_created") {
            clearPendingFriendRemoved(typedEvent.conversation_id);
          }
        }
        let keys: string[];
        if (typedEvent.type === "meal.list.updated") {
          keys = [subscriptionKey("meal-list")];
        } else if (typedEvent.type === "social.updated") {
          keys = [subscriptionKey("conversation-list")];
        } else if (
          typedEvent.type === "conversation.updated" ||
          typedEvent.type === "conversation.deleted"
        ) {
          keys = [
            subscriptionKey("conversation-list"),
            subscriptionKey("chat", undefined, typedEvent.conversation_id),
          ];
        } else if (
          typedEvent.type === "message.created" ||
          typedEvent.type === "message.recalled" ||
          typedEvent.type === "message.pinned" ||
          typedEvent.type === "message.unpinned" ||
          typedEvent.type === "conversation.read" ||
          typedEvent.type === "typing.updated"
        ) {
          keys = [
            subscriptionKey(
              "chat",
              "meal_id" in typedEvent && typedEvent.meal_id ? typedEvent.meal_id : undefined,
              typedEvent.conversation_id,
            ),
          ];
        } else {
          keys = [subscriptionKey("state", typedEvent.meal_id ?? undefined)];
        }
        const notified = new Set<(event: RealtimeEvent) => void>();
        for (const key of keys) {
          for (const listener of subscriptionsRef.current.get(key)?.listeners ?? []) {
            if (!notified.has(listener)) {
              notified.add(listener);
              listener(typedEvent);
            }
          }
        }
      });

      socket.addEventListener("close", () => {
        if (socketRef.current !== socket) return;
        readyRef.current = false;
        socketRef.current = null;
        if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer);
        heartbeatTimer = null;
        rejectPending();
        if (disposed) return;
        setStatus("disconnected");
        const delay = Math.min(1_000 * 2 ** attempt, 30_000) + Math.random() * 250;
        attempt += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      });
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer);
      rejectPending();
      const socket = socketRef.current;
      socketRef.current = null;
      readyRef.current = false;
      socket?.close(1000, "page closed");
    };
  }, [sendSubscription]);

  const subscribe = useCallback(
    (
      channel: RealtimeChannel,
      mealId: string | undefined,
      listener: (event: RealtimeEvent) => void,
    ) => {
      const key = subscriptionKey(channel, mealId);
      let subscription = subscriptionsRef.current.get(key);
      if (!subscription) {
        subscription = { channel, mealId, listeners: new Set() };
        subscriptionsRef.current.set(key, subscription);
        sendSubscription(subscription, "subscribe");
      }
      subscription.listeners.add(listener);
      return () => {
        const current = subscriptionsRef.current.get(key);
        if (!current) return;
        current.listeners.delete(listener);
        if (current.listeners.size === 0) {
          sendSubscription(current, "unsubscribe");
          subscriptionsRef.current.delete(key);
        }
      };
    },
    [sendSubscription],
  );

  const subscribeConversation = useCallback(
    (conversationId: string, listener: (event: RealtimeEvent) => void) => {
      const key = subscriptionKey("chat", undefined, conversationId);
      let subscription = subscriptionsRef.current.get(key);
      if (!subscription) {
        subscription = { channel: "chat", conversationId, listeners: new Set() };
        subscriptionsRef.current.set(key, subscription);
        sendSubscription(subscription, "subscribe");
      }
      subscription.listeners.add(listener);
      return () => {
        const current = subscriptionsRef.current.get(key);
        if (!current) return;
        current.listeners.delete(listener);
        if (current.listeners.size === 0) {
          sendSubscription(current, "unsubscribe");
          subscriptionsRef.current.delete(key);
        }
      };
    },
    [sendSubscription],
  );

  const sendMessage = useCallback(
    (mealId: string, content: string, replyToMessageId?: string | null) => {
      const socket = socketRef.current;
      if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) {
        return Promise.reject(new Error("即時連線尚未恢復，請稍後再試。"));
      }
      const requestId = crypto.randomUUID();
      return new Promise<string>((resolve, reject) => {
        const timer = window.setTimeout(() => {
          pendingRef.current.delete(requestId);
          reject(new Error("訊息傳送逾時，請重新送出。"));
        }, 10_000);
        pendingRef.current.set(requestId, { resolve, reject, timer });
        socket.send(
          JSON.stringify({
            type: "message.send",
            request_id: requestId,
            meal_id: mealId,
            content,
            ...(replyToMessageId ? { reply_to_message_id: replyToMessageId } : {}),
          }),
        );
      });
    },
    [],
  );

  const sendDirectMessage = useCallback(
    (conversationId: string, content: string, replyToMessageId?: string | null) => {
      const socket = socketRef.current;
      if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) {
        return Promise.reject(new Error("即時連線尚未恢復，請稍後再試。"));
      }
      const requestId = crypto.randomUUID();
      return new Promise<string>((resolve, reject) => {
        const timer = window.setTimeout(() => {
          pendingRef.current.delete(requestId);
          reject(new Error("訊息傳送逾時，請重新送出。"));
        }, 10_000);
        pendingRef.current.set(requestId, { resolve, reject, timer });
        socket.send(
          JSON.stringify({
            type: "message.send",
            request_id: requestId,
            conversation_id: conversationId,
            content,
            ...(replyToMessageId ? { reply_to_message_id: replyToMessageId } : {}),
          }),
        );
      });
    },
    [],
  );

  const sendRequest = useCallback((payload: Record<string, string>) => {
    const socket = socketRef.current;
    if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("即時連線尚未恢復，請稍後再試。"));
    }
    const requestId = crypto.randomUUID();
    return new Promise<string>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        pendingRef.current.delete(requestId);
        reject(new Error("即時操作逾時，請重新再試。"));
      }, 10_000);
      pendingRef.current.set(requestId, { resolve, reject, timer });
      socket.send(JSON.stringify({ ...payload, request_id: requestId }));
    });
  }, []);

  const sendConversationRead = useCallback(
    (conversationId: string, messageId: string) =>
      sendRequest({
        type: "conversation.read",
        conversation_id: conversationId,
        message_id: messageId,
      }),
    [sendRequest],
  );

  const sendTyping = useCallback((conversationId: string, isTyping: boolean) => {
    const socket = socketRef.current;
    if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(
      JSON.stringify({
        type: isTyping ? "typing.start" : "typing.stop",
        conversation_id: conversationId,
      }),
    );
  }, []);

  const sendMealTyping = useCallback((mealId: string, isTyping: boolean) => {
    const socket = socketRef.current;
    if (!readyRef.current || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(
      JSON.stringify({
        type: isTyping ? "typing.start" : "typing.stop",
        meal_id: mealId,
      }),
    );
  }, []);

  const recallMessage = useCallback(
    (conversationId: string, messageId: string) =>
      sendRequest({
        type: "message.recall",
        conversation_id: conversationId,
        message_id: messageId,
      }),
    [sendRequest],
  );

  const pinMessage = useCallback(
    (conversationId: string, messageId: string) =>
      sendRequest({
        type: "message.pin",
        conversation_id: conversationId,
        message_id: messageId,
      }),
    [sendRequest],
  );

  const unpinMessage = useCallback(
    (conversationId: string, messageId: string) =>
      sendRequest({
        type: "message.unpin",
        conversation_id: conversationId,
        message_id: messageId,
      }),
    [sendRequest],
  );

  const value = useMemo(
    () => ({
      status,
      subscribe,
      subscribeConversation,
      sendMessage,
      sendDirectMessage,
      sendConversationRead,
      sendTyping,
      sendMealTyping,
      recallMessage,
      pinMessage,
      unpinMessage,
    }),
    [
      recallMessage,
      sendConversationRead,
      sendDirectMessage,
      sendMessage,
      sendMealTyping,
      sendTyping,
      status,
      subscribe,
      subscribeConversation,
      pinMessage,
      unpinMessage,
    ],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime() {
  const context = useContext(RealtimeContext);
  if (!context) throw new Error("useRealtime must be used inside RealtimeProvider");
  return context;
}
