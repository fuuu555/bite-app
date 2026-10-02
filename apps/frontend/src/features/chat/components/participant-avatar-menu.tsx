"use client";

import { IconMessageCircle, IconUserCircle } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { createDirectConversation } from "@/features/chat/api/chat-api";
import { Profile, UserApiError, userApi } from "@/shared/auth/user-api";

type ParticipantAvatarMenuProps = {
  userId: string;
  displayName: string;
  avatarUrl: string | null;
  className?: string;
};

export function ParticipantAvatarMenu({
  userId,
  displayName,
  avatarUrl,
  className = "",
}: ParticipantAvatarMenuProps) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const canMessage = profile?.relationship?.can_message === true;
  const isFriend = profile?.relationship?.status === "friends";
  const isStrangerMessage = Boolean(profile?.relationship && !isFriend && canMessage);
  const messageUnavailable = profile?.relationship && !profile.relationship.can_message;

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const updatePosition = () => {
      const bounds = rootRef.current?.getBoundingClientRect();
      if (!bounds) return;
      // The menu is portalled so a chat scroller cannot clip its controls.
      // 選單掛到頁面根節點，避免被聊天室的捲動容器裁切。
      setPosition({
        top: bounds.bottom + 8,
        left: Math.max(12, Math.min(bounds.left, window.innerWidth - 190)),
      });
    };
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  async function toggleMenu() {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (!nextOpen || profile || loading) return;
    setLoading(true);
    setError("");
    try {
      setProfile(await userApi<Profile>(`/profiles/${userId}`));
    } catch (caught) {
      setError(
        caught instanceof UserApiError && caught.status === 403
          ? "目前無法查看這位使用者的社交設定。"
          : "目前無法取得私聊設定。",
      );
    } finally {
      setLoading(false);
    }
  }

  function viewProfile() {
    router.push(profile?.relationship?.status === "self" ? "/profile" : `/profiles/${userId}`);
    setOpen(false);
  }

  async function openPrivateChat() {
    if (!canMessage) return;
    try {
      const conversation = await createDirectConversation(userId);
      router.push(`/chat?category=chat&conversation=${conversation.conversation_id}`);
      setOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "目前無法開啟私聊。");
    }
  }

  const menu = open ? (
    <div className="participant-avatar-menu__popover" ref={menuRef} role="menu" style={position}>
      <button type="button" role="menuitem" onClick={viewProfile}>
        <IconUserCircle aria-hidden="true" /> 查看個人資料
      </button>
      <div className="participant-avatar-menu__message-action">
        <button
          type="button"
          role="menuitem"
          className={messageUnavailable ? "is-disabled" : undefined}
          disabled={loading || Boolean(messageUnavailable) || Boolean(error)}
          onClick={() => void openPrivateChat()}
          title={messageUnavailable ? "對方已關閉陌生人私聊" : undefined}
        >
          <IconMessageCircle aria-hidden="true" />
          {loading
            ? "檢查私聊設定…"
            : messageUnavailable
              ? "私聊（對方已關閉）"
              : error
                ? "私聊設定無法取得"
                : isFriend
                  ? "聊天"
                  : "私聊"}
        </button>
        {isStrangerMessage ? <small>陌生人私聊</small> : null}
      </div>
      {messageUnavailable ? <small>對方已關閉陌生人私聊</small> : null}
      {error ? <small role="alert">{error}</small> : null}
    </div>
  ) : null;

  return (
    <div className={`participant-avatar-menu ${className}`.trim()} ref={rootRef}>
      <button
        type="button"
        className="participant-avatar-menu__trigger"
        aria-label={`開啟 ${displayName} 的操作選單`}
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation();
          void toggleMenu();
        }}
      >
        {avatarUrl ? (
          // Avatar URLs are validated by the public profile API contract.
          // 頭像網址已由公開個人資料 API 契約驗證。
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt="" />
        ) : (
          <span aria-hidden="true">{displayName.slice(0, 1)}</span>
        )}
      </button>
      {typeof document !== "undefined" && menu ? createPortal(menu, document.body) : null}
    </div>
  );
}
