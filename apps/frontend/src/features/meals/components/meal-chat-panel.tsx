"use client";

import { ConversationChatPanel } from "@/features/chat/components/conversation-chat-panel";

export function MealChatPanel({ mealId }: { mealId: string }) {
  return (
    <ConversationChatPanel
      mealId={mealId}
      title="飯局聊天室"
      ariaLabel="飯局聊天室"
      placeholder="和飯友說點什麼…"
      emptyMessage="還沒有訊息，先和飯友打聲招呼吧。"
    />
  );
}
