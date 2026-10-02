/** Friend and block relationship API client / 好友與封鎖關係 API Client。 */

import { userApi } from "@/shared/auth/user-api";
import type { Profile, Relationship } from "@/shared/auth/user-api";

export type FriendRequest = {
  id: string;
  requester_id: string;
  recipient_id: string;
  status: "pending" | "accepted" | "rejected" | "cancelled";
  created_at: string;
  responded_at: string | null;
};

export type SocialAction = {
  relationship: Relationship;
  request: FriendRequest | null;
};

export type FollowSummary = Pick<
  FriendSummary,
  "id" | "display_name" | "avatar_url" | "avatar_source" | "avatar_asset_id"
> & { created_at: string };

export type FriendSummary = Pick<
  Profile,
  "id" | "display_name" | "avatar_url" | "avatar_source" | "avatar_asset_id"
> & {
  conversation_id: string | null;
};

export type FriendLookup = FriendSummary & {
  relationship: Relationship;
};

export function fetchFriends(signal?: AbortSignal) {
  return userApi<FriendSummary[]>("/friends", { signal });
}

export function lookupFriendCode(code: string, signal?: AbortSignal) {
  return userApi<FriendLookup>(`/users/lookup?friend_code=${encodeURIComponent(code)}`, {
    signal,
  });
}

export function sendFriendRequest(userId: string) {
  return userApi<SocialAction>("/friend-requests", {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export function acceptFriendRequest(requestId: string) {
  return userApi<SocialAction>(`/friend-requests/${requestId}/accept`, { method: "POST" });
}

export function rejectFriendRequest(requestId: string) {
  return userApi<SocialAction>(`/friend-requests/${requestId}/reject`, { method: "POST" });
}

export function cancelFriendRequest(requestId: string) {
  return userApi<SocialAction>(`/friend-requests/${requestId}/cancel`, { method: "POST" });
}

export function removeFriend(userId: string) {
  return userApi<Relationship>(`/friends/${userId}`, { method: "DELETE" });
}

export function blockUser(userId: string) {
  return userApi<Relationship>(`/blocks/${userId}`, { method: "POST" });
}

export function unblockUser(userId: string) {
  return userApi<Relationship>(`/blocks/${userId}`, { method: "DELETE" });
}

export function followUser(userId: string) {
  return userApi<Relationship>(`/users/${userId}/follow`, { method: "POST" });
}

export function unfollowUser(userId: string) {
  return userApi<Relationship>(`/users/${userId}/follow`, { method: "DELETE" });
}

export function fetchFollowing(signal?: AbortSignal) {
  return userApi<FollowSummary[]>("/me/following", { signal });
}

export function fetchFollowers(signal?: AbortSignal) {
  return userApi<FollowSummary[]>("/me/followers", { signal });
}
