export type ChatCategory = "chat" | "meal" | "friends";

export function resolveChatCategory(value: string | null): ChatCategory {
  return value === "meal" || value === "friends" ? value : "chat";
}
