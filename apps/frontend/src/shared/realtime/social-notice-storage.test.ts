import { describe, expect, it } from "vitest";

import {
  clearPendingFriendRemoved,
  hasPendingFriendRemoved,
  rememberFriendRemoved,
} from "./social-notice-storage";

function createStore() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };
}

describe("friend removal notice storage", () => {
  it("remembers and clears a notice by conversation", () => {
    const store = createStore();

    expect(hasPendingFriendRemoved("conversation-1", store)).toBe(false);

    rememberFriendRemoved("conversation-1", store);
    expect(hasPendingFriendRemoved("conversation-1", store)).toBe(true);
    expect(hasPendingFriendRemoved("conversation-2", store)).toBe(false);

    clearPendingFriendRemoved("conversation-1", store);
    expect(hasPendingFriendRemoved("conversation-1", store)).toBe(false);
  });

  it("does not throw when storage is unavailable", () => {
    expect(() => rememberFriendRemoved("conversation-1", null)).not.toThrow();
    expect(hasPendingFriendRemoved("conversation-1", null)).toBe(false);
    expect(() => clearPendingFriendRemoved("conversation-1", null)).not.toThrow();
  });
});
