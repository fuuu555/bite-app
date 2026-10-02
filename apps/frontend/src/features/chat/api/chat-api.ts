/** Persistent chat REST client / 永久聊天 REST Client。 */

import type { MessageCreatedEvent } from "@/shared/realtime/realtime";

export type ChatMessage = MessageCreatedEvent["message"];

export type ConversationSummary = {
  conversation_id: string;
  kind: "meal" | "direct";
  category: "meal" | "direct" | "friends";
  meal_id?: string | null;
  meal_title?: string | null;
  meal_status?:
    "open" | "awaiting_host_decision" | "voting" | "decided" | "cancelled" | "completed" | null;
  other_user?: ChatMessage["sender"] | null;
  latest_message: ChatMessage | null;
  unread_count: number;
};

export type MealConversation = ConversationSummary & {
  meal_id: string;
  meal_title: string;
  meal_status: NonNullable<ConversationSummary["meal_status"]>;
};

export class ChatApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "聊天資料暫時無法載入");
  }
}

async function chatApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "include",
    ...init,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new ChatApiError(response.status, payload.detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fetchMealMessages(mealId: string, cursor?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  return chatApi<{ messages: ChatMessage[]; next_cursor: string | null }>(
    `/meals/${encodeURIComponent(mealId)}/messages?${query}`,
    { signal },
  );
}

export function fetchConversationMessages(
  conversationId: string,
  cursor?: string,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  return chatApi<{ messages: ChatMessage[]; next_cursor: string | null }>(
    `/conversations/${encodeURIComponent(conversationId)}/messages?${query}`,
    { signal },
  );
}

export function fetchMealPinnedMessages(mealId: string, signal?: AbortSignal) {
  return chatApi<{ messages: ChatMessage[] }>(`/meals/${encodeURIComponent(mealId)}/pins`, {
    signal,
  });
}

export function fetchPinnedMessages(conversationId: string, signal?: AbortSignal) {
  return chatApi<{ messages: ChatMessage[] }>(
    `/conversations/${encodeURIComponent(conversationId)}/pins`,
    { signal },
  );
}

export function fetchMealConversations(signal?: AbortSignal) {
  return chatApi<{ conversations: MealConversation[] }>("/conversations?kind=meal", { signal });
}

export function fetchDirectConversations(category: "direct" | "friends", signal?: AbortSignal) {
  return chatApi<{ conversations: ConversationSummary[] }>(`/conversations?kind=${category}`, {
    signal,
  });
}

export function createDirectConversation(userId: string) {
  return chatApi<{ conversation_id: string; other_user: ChatMessage["sender"] }>(
    `/conversations/direct/${encodeURIComponent(userId)}`,
    { method: "POST" },
  );
}

export function deleteConversation(conversationId: string) {
  return chatApi<void>(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
}

export function markConversationRead(conversationId: string, messageId: string) {
  return chatApi<{ conversation_id: string; message_id: string; read_at: string }>(
    `/conversations/${encodeURIComponent(conversationId)}/read`,
    {
      method: "POST",
      body: JSON.stringify({ message_id: messageId }),
      headers: { "Content-Type": "application/json" },
    },
  );
}
