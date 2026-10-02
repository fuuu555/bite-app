import { describe, expect, it } from "vitest";

import { resolveChatCategory } from "./chat-navigation";

describe("resolveChatCategory", () => {
  it("keeps supported chat categories", () => {
    expect(resolveChatCategory("chat")).toBe("chat");
    expect(resolveChatCategory("meal")).toBe("meal");
    expect(resolveChatCategory("friends")).toBe("friends");
  });

  it("falls back to the chat category for unknown values", () => {
    expect(resolveChatCategory(null)).toBe("chat");
    expect(resolveChatCategory("unknown")).toBe("chat");
  });
});
