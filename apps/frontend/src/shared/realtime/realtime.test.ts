import { describe, expect, it } from "vitest";

import { resolveWebSocketUrl } from "./realtime";

describe("resolveWebSocketUrl", () => {
  it("uses a configured WebSocket endpoint when provided", () => {
    expect(resolveWebSocketUrl("https://bite.example/meals", "wss://api.example/ws")).toBe(
      "wss://api.example/ws",
    );
  });

  it("derives ws and wss endpoints from the current origin", () => {
    expect(resolveWebSocketUrl("http://localhost:3000/meals")).toBe(
      "ws://localhost:3000/api/v1/ws",
    );
    expect(resolveWebSocketUrl("https://bite.example/chat")).toBe("wss://bite.example/api/v1/ws");
  });
});
