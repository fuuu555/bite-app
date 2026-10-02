/** General-user account API client / 一般使用者帳號 API Client。 */

export type ProfileTag = {
  id: string;
  slug: string;
  display_name: string;
  is_system: boolean;
};

export type User = {
  id: string;
  email: string;
  role: "user";
};

export type Relationship = {
  status:
    | "self"
    | "none"
    | "friends"
    | "outgoing_pending"
    | "incoming_pending"
    | "blocked_by_me"
    | "blocked_me";
  request_id: string | null;
  conversation_id: string | null;
  can_message: boolean;
  can_add_friend: boolean;
  can_accept_friend_request: boolean;
  follow_status: "none" | "following" | "followed_by" | "mutual";
};

export type Profile = {
  id: string;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  avatar_source: "builtin" | "google" | "url";
  avatar_asset_id: string | null;
  tags: ProfileTag[];
  accept_stranger_messages: boolean;
  relationship?: Relationship | null;
};

export type AvatarAsset = {
  id: string;
  display_name: string;
  url: string;
  mime_type: string;
  file_size: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MyProfile = Profile & {
  email: string;
  friend_code: string;
};

export type UserSession = {
  id: string;
  device_label: string;
  expires_at: string;
  last_seen_at: string;
  created_at: string;
  current: boolean;
};

export class UserApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : "Request failed");
  }
}

export async function userApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new UserApiError(response.status, payload.detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function fetchAvatarAssets() {
  return userApi<AvatarAsset[]>("/avatar-assets");
}

export const suggestedProfileTags = [
  "甜食控",
  "拉麵控",
  "咖啡愛好者",
  "火鍋控",
  "肉食派",
  "探店愛好者",
  "台式小吃",
  "日式料理",
  "韓式料理",
  "素食友善",
];
