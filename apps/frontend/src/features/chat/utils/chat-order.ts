/** Stable chronological message merge / 穩定的聊天訊息時間排序與合併。 */

import type { ChatMessage } from "@/features/chat/api/chat-api";

export function compareChatMessages(left: ChatMessage, right: ChatMessage) {
  const timestampOrder = Date.parse(left.created_at) - Date.parse(right.created_at);
  if (timestampOrder !== 0) return timestampOrder;
  if (left.id === right.id) return 0;
  return left.id < right.id ? -1 : 1;
}

export function sortChatMessages(messages: ChatMessage[]) {
  return [...messages].sort(compareChatMessages);
}

export function mergeChatMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return sortChatMessages([...byId.values()]);
}
