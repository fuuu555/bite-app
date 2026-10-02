type SessionStore = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const FRIEND_REMOVED_KEY_PREFIX = "bitemap:chat:friend-removed:";

function getSessionStore(): SessionStore | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function friendRemovedKey(conversationId: string) {
  return `${FRIEND_REMOVED_KEY_PREFIX}${conversationId}`;
}

export function rememberFriendRemoved(
  conversationId: string,
  store: SessionStore | null = getSessionStore(),
) {
  if (!store) return;
  try {
    // The conversation id is the scope; no relationship details are persisted.
    // 僅用聊天室 ID 標記待確認狀態，不在瀏覽器保存其他關係資料。
    store.setItem(friendRemovedKey(conversationId), "1");
  } catch {
    // A disabled or full session store must not break realtime event handling.
  }
}

export function hasPendingFriendRemoved(
  conversationId: string,
  store: SessionStore | null = getSessionStore(),
) {
  if (!store) return false;
  try {
    return store.getItem(friendRemovedKey(conversationId)) === "1";
  } catch {
    return false;
  }
}

export function clearPendingFriendRemoved(
  conversationId: string,
  store: SessionStore | null = getSessionStore(),
) {
  if (!store) return;
  try {
    store.removeItem(friendRemovedKey(conversationId));
  } catch {
    // Storage failures are non-fatal; the server remains the relationship authority.
  }
}
