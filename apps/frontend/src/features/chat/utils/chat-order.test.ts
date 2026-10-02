import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/features/chat/api/chat-api";
import { mergeChatMessages, sortChatMessages } from "./chat-order";

const sender = { user_id: "user-1", display_name: "測試者", avatar_url: null };

function message(id: string, created_at: string, content = id): ChatMessage {
  return {
    id,
    conversation_id: "conversation-1",
    conversation_kind: "direct",
    meal_id: null,
    sender,
    content,
    created_at,
  };
}

describe("chat message ordering", () => {
  it("sorts by server time and uses id as a stable tie-breaker", () => {
    const sameTime = "2026-10-02T04:00:00.000000Z";
    expect(
      sortChatMessages([
        message("b", sameTime),
        message("later", "2026-10-02T04:00:01.000000Z"),
        message("a", sameTime),
      ]).map((item) => item.id),
    ).toEqual(["a", "b", "later"]);
  });

  it("deduplicates messages while merging out-of-order realtime events", () => {
    const first = message("first", "2026-10-02T04:00:00.000000Z");
    const second = message("second", "2026-10-02T04:00:01.000000Z");
    expect(mergeChatMessages([second], [first, second]).map((item) => item.id)).toEqual([
      "first",
      "second",
    ]);
  });
});
