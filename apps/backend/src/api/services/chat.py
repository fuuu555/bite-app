"""Persistent meal chat services and authorization / 永久飯局聊天服務與權限。"""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import (
    Conversation,
    ConversationMember,
    DirectConversationPair,
    MealEvent,
    MealMembership,
    Message,
    MessagePin,
    User,
    UserProfile,
)
from api.domain.schemas import (
    ChatAuthorResponse,
    ConversationListResponse,
    ConversationReadResponse,
    ConversationResponse,
    DirectConversationResponse,
    MealStatus,
    MessagePageResponse,
    MessageReplyResponse,
    MessageResponse,
    PinnedMessagesResponse,
)
from api.services.meals import FORMAL_MEMBERSHIP_STATUSES, LIVE_MEAL_STATUSES
from api.services.profile import avatar_url_for_profile
from api.services.social import block_direction, canonical_pair, has_friendship


def _message_options():
    return (
        selectinload(Message.sender)
        .selectinload(User.profile)
        .options(selectinload(UserProfile.avatar_asset)),
        selectinload(Message.conversation),
        selectinload(Message.reply_to)
        .selectinload(Message.sender)
        .selectinload(User.profile)
        .options(selectinload(UserProfile.avatar_asset)),
        selectinload(Message.pin).selectinload(MessagePin.pinned_by),
    )


async def ensure_meal_conversation(session: AsyncSession, meal_id: uuid.UUID) -> Conversation:
    """Return the unique room for a meal, creating it in the current transaction if needed."""
    conversation = await session.scalar(
        select(Conversation).where(Conversation.meal_event_id == meal_id)
    )
    if conversation is None:
        conversation = Conversation(kind="meal", meal_event_id=meal_id)
        session.add(conversation)
        await session.flush()
    return conversation


async def sync_meal_conversation_member(
    session: AsyncSession,
    meal_id: uuid.UUID,
    user_id: uuid.UUID,
    membership_status: str,
) -> None:
    """Mirror participation history while leaving authorization to meal membership."""
    conversation = await ensure_meal_conversation(session, meal_id)
    member = await session.get(
        ConversationMember,
        {"conversation_id": conversation.id, "user_id": user_id},
    )
    is_formal = membership_status in FORMAL_MEMBERSHIP_STATUSES
    now = datetime.now(UTC)
    if member is None and is_formal:
        session.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user_id,
                joined_at=now,
            )
        )
    elif member is not None:
        member.left_at = None if is_formal else now


async def meal_subscription_permissions(
    session: AsyncSession, meal_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[bool, bool]:
    """Return state and chat subscription permissions / 回傳狀態與聊天訂閱權限。"""
    row = (
        await session.execute(
            select(MealEvent.visibility, MealEvent.status, MealMembership.membership_status)
            .outerjoin(
                MealMembership,
                and_(
                    MealMembership.meal_event_id == MealEvent.id,
                    MealMembership.user_id == user_id,
                ),
            )
            .where(MealEvent.id == meal_id)
        )
    ).one_or_none()
    if row is None or row.status not in LIVE_MEAL_STATUSES:
        return False, False
    membership_status = row.membership_status
    can_chat = membership_status in FORMAL_MEMBERSHIP_STATUSES
    can_view_state = row.visibility == "public" or membership_status in (
        *FORMAL_MEMBERSHIP_STATUSES,
        "pending",
    )
    return can_view_state, can_chat


async def formal_meal_member_ids(session: AsyncSession, meal_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(MealMembership.user_id).where(
                    MealMembership.meal_event_id == meal_id,
                    MealMembership.membership_status.in_(FORMAL_MEMBERSHIP_STATUSES),
                )
            )
        ).all()
    )


async def private_meal_state_audience(
    session: AsyncSession,
    meal_id: uuid.UUID,
    extra_user_ids: set[uuid.UUID] | None = None,
) -> list[uuid.UUID] | None:
    """Return a private audience, or None for public broadcast / 私人受眾；公開則回傳 None。"""
    meal = await session.get(MealEvent, meal_id)
    if meal is None or meal.visibility == "public":
        return None
    audience = set(
        (
            await session.scalars(
                select(MealMembership.user_id).where(
                    MealMembership.meal_event_id == meal_id,
                    MealMembership.membership_status.in_(("host", "member", "pending")),
                )
            )
        ).all()
    )
    audience.update(extra_user_ids or set())
    return sorted(audience, key=str)


def message_response(message: Message, current_user_id: uuid.UUID | None = None) -> MessageResponse:
    profile = message.sender.profile
    meal_id = message.conversation.meal_event_id
    is_recalled = message.recalled_at is not None
    content = "" if is_recalled else message.content
    can_recall = (
        message.sender_user_id == current_user_id
        and not is_recalled
        and (datetime.now(UTC) - message.created_at).total_seconds() <= 120
    )
    sender = ChatAuthorResponse(
        user_id=message.sender_user_id,
        display_name=(profile.display_name if profile else message.sender.email.split("@", 1)[0]),
        avatar_url=avatar_url_for_profile(profile) if profile else None,
    )
    reply_to = None
    if message.reply_to is not None:
        reply_profile = message.reply_to.sender.profile
        reply_to = MessageReplyResponse(
            id=message.reply_to.id,
            sender=ChatAuthorResponse(
                user_id=message.reply_to.sender_user_id,
                display_name=(
                    reply_profile.display_name
                    if reply_profile
                    else message.reply_to.sender.email.split("@", 1)[0]
                ),
                avatar_url=avatar_url_for_profile(reply_profile) if reply_profile else None,
            ),
            content=("" if message.reply_to.recalled_at is not None else message.reply_to.content),
            is_recalled=message.reply_to.recalled_at is not None,
        )
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        conversation_kind="meal" if meal_id is not None else "direct",
        meal_id=meal_id,
        sender=sender,
        content=content,
        created_at=message.created_at,
        is_recalled=is_recalled,
        recalled_at=message.recalled_at,
        can_recall=can_recall,
        is_mine=message.sender_user_id == current_user_id,
        reply_to=reply_to,
        is_pinned=message.pin is not None,
        pinned_at=message.pin.pinned_at if message.pin else None,
        can_pin=current_user_id is not None,
    )


def _encode_cursor(message: Message) -> str:
    raw = f"{message.created_at.isoformat()}|{message.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        created_text, message_id_text = decoded.rsplit("|", 1)
        created_at = datetime.fromisoformat(created_text)
        if created_at.tzinfo is None:
            raise ValueError("cursor timestamp needs a timezone")
        return created_at, uuid.UUID(message_id_text)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise ValueError("invalid message cursor") from error


async def read_meal_messages(
    session: AsyncSession,
    meal_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: str | None,
    limit: int,
) -> MessagePageResponse:
    """Read one reverse page and return it chronologically / 反向分頁後依時間正序回傳。"""
    _, can_chat = await meal_subscription_permissions(session, meal_id, user_id)
    if not can_chat:
        raise PermissionError("formal meal membership required")
    conversation = await session.scalar(
        select(Conversation).where(Conversation.meal_event_id == meal_id)
    )
    if conversation is None:
        raise LookupError("meal conversation not found")

    statement = (
        select(Message)
        .options(*_message_options())
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        created_at, message_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                Message.created_at < created_at,
                and_(Message.created_at == created_at, Message.id < message_id),
            )
        )
    rows = list((await session.scalars(statement)).all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1]) if has_more and page else None
    return MessagePageResponse(
        messages=[message_response(message, user_id) for message in reversed(page)],
        next_cursor=next_cursor,
    )


async def read_conversation_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: str | None,
    limit: int,
) -> MessagePageResponse:
    """Read authorized meal or direct history / 讀取已授權的飯局或私訊歷史。"""
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if conversation is None:
        raise LookupError("conversation not found")
    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if member is None:
        raise PermissionError("conversation membership required")
    if conversation.kind == "direct":
        target_id = await direct_target_user_id(session, conversation_id, user_id)
        current_blocks, target_blocks = await block_direction(session, user_id, target_id)
        if current_blocks or target_blocks:
            raise PermissionError("conversation is not available")
    elif conversation.meal_event_id is not None:
        _, can_chat = await meal_subscription_permissions(
            session, conversation.meal_event_id, user_id
        )
        if not can_chat:
            raise PermissionError("formal meal membership required")
    statement = (
        select(Message)
        .options(*_message_options())
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        created_at, message_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                Message.created_at < created_at,
                and_(Message.created_at == created_at, Message.id < message_id),
            )
        )
    rows = list((await session.scalars(statement)).all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1]) if has_more and page else None
    return MessagePageResponse(
        messages=[message_response(message, user_id) for message in reversed(page)],
        next_cursor=next_cursor,
    )


async def create_meal_message(
    session: AsyncSession,
    meal_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    reply_to_message_id: uuid.UUID | None = None,
) -> MessageResponse:
    """Persist a validated message before it can be broadcast / 驗證並先保存再廣播。"""
    normalized = content.strip()
    if not normalized:
        raise ValueError("message cannot be empty")
    if len(normalized) > 2000:
        raise ValueError("message cannot exceed 2000 characters")
    _, can_chat = await meal_subscription_permissions(session, meal_id, user_id)
    if not can_chat:
        raise PermissionError("formal meal membership required")
    conversation = await ensure_meal_conversation(session, meal_id)
    reply_to_message_id = await _validate_reply_target(
        session, conversation.id, reply_to_message_id
    )
    await sync_meal_conversation_member(session, meal_id, user_id, "member")
    message = Message(
        conversation_id=conversation.id,
        sender_user_id=user_id,
        reply_to_message_id=reply_to_message_id,
        content=normalized,
    )
    session.add(message)
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    stored = await session.scalar(
        select(Message).options(*_message_options()).where(Message.id == message.id)
    )
    if stored is None:
        raise RuntimeError("stored message could not be loaded")
    return message_response(stored, user_id)


async def list_meal_conversations(
    session: AsyncSession, user_id: uuid.UUID
) -> ConversationListResponse:
    conversations = list(
        (
            await session.scalars(
                select(Conversation)
                .join(MealEvent, MealEvent.id == Conversation.meal_event_id)
                .join(
                    MealMembership,
                    and_(
                        MealMembership.meal_event_id == MealEvent.id,
                        MealMembership.user_id == user_id,
                    ),
                )
                .where(
                    Conversation.kind == "meal",
                    MealEvent.status.in_(LIVE_MEAL_STATUSES),
                    MealMembership.membership_status.in_(FORMAL_MEMBERSHIP_STATUSES),
                )
                .options(selectinload(Conversation.meal), selectinload(Conversation.members))
                .order_by(Conversation.updated_at.desc())
            )
        ).all()
    )
    responses: list[ConversationResponse] = []
    for conversation in conversations:
        latest = await session.scalar(
            select(Message)
            .options(*_message_options())
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        meal = conversation.meal
        if meal is None:
            continue
        responses.append(
            ConversationResponse(
                conversation_id=conversation.id,
                kind="meal",
                category="meal",
                meal_id=meal.id,
                meal_title=meal.title,
                meal_status=cast(MealStatus, meal.status),
                latest_message=message_response(latest, user_id) if latest else None,
                unread_count=await unread_count(session, conversation.id, user_id),
            )
        )
    return ConversationListResponse(conversations=responses)


async def list_direct_conversations(
    session: AsyncSession,
    user_id: uuid.UUID,
    category: str,
) -> ConversationListResponse:
    conversations = list(
        (
            await session.scalars(
                select(Conversation)
                .join(
                    ConversationMember,
                    and_(
                        ConversationMember.conversation_id == Conversation.id,
                        ConversationMember.user_id == user_id,
                        ConversationMember.left_at.is_(None),
                    ),
                )
                .where(Conversation.kind == "direct")
                .options(
                    selectinload(Conversation.members)
                    .selectinload(ConversationMember.user)
                    .selectinload(User.profile)
                    .options(selectinload(UserProfile.avatar_asset))
                )
                .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            )
        ).all()
    )
    responses: list[ConversationResponse] = []
    for conversation in conversations:
        other_member = next(
            (member for member in conversation.members if member.user_id != user_id), None
        )
        if other_member is None:
            continue
        current_blocks, target_blocks = await block_direction(
            session, user_id, other_member.user_id
        )
        if current_blocks or target_blocks:
            continue
        is_friend = await has_friendship(session, user_id, other_member.user_id)
        actual_category = "friends" if is_friend else "direct"
        if category != actual_category:
            continue
        latest = await session.scalar(
            select(Message)
            .options(*_message_options())
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        profile = other_member.user.profile
        responses.append(
            ConversationResponse(
                conversation_id=conversation.id,
                kind="direct",
                category=actual_category,
                other_user=ChatAuthorResponse(
                    user_id=other_member.user_id,
                    display_name=(
                        profile.display_name
                        if profile
                        else other_member.user.email.split("@", 1)[0]
                    ),
                    avatar_url=avatar_url_for_profile(profile) if profile else None,
                ),
                latest_message=message_response(latest, user_id) if latest else None,
                unread_count=await unread_count(session, conversation.id, user_id),
            )
        )
    return ConversationListResponse(conversations=responses)


async def ensure_direct_conversation(
    session: AsyncSession, current_user_id: uuid.UUID, target_user_id: uuid.UUID
) -> DirectConversationResponse:
    """Find or create one direct room after block checks / 驗證封鎖後取得或建立私訊房間。"""
    if current_user_id == target_user_id:
        raise ValueError("cannot message yourself")
    target_exists = await session.scalar(
        select(User.id).where(
            User.id == target_user_id,
            User.role == "user",
            User.is_active.is_(True),
        )
    )
    if target_exists is None:
        raise LookupError("user not found")
    first_blocks, second_blocks = await block_direction(session, current_user_id, target_user_id)
    if first_blocks or second_blocks:
        raise PermissionError("direct conversation is not allowed")
    low, high = canonical_pair(current_user_id, target_user_id)
    pair = await session.scalar(
        select(DirectConversationPair).where(
            DirectConversationPair.user_low_id == low,
            DirectConversationPair.user_high_id == high,
        )
    )
    if pair is None:
        conversation = Conversation(kind="direct")
        session.add(conversation)
        await session.flush()
        pair = DirectConversationPair(
            user_low_id=low,
            user_high_id=high,
            conversation_id=conversation.id,
        )
        session.add(pair)
        session.add_all(
            [
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=current_user_id,
                ),
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=target_user_id,
                ),
            ]
        )
        await session.commit()
    conversation = await session.scalar(
        select(Conversation)
        .options(
            selectinload(Conversation.members)
            .selectinload(ConversationMember.user)
            .selectinload(User.profile)
            .options(selectinload(UserProfile.avatar_asset))
        )
        .where(Conversation.id == pair.conversation_id)
    )
    if conversation is None:
        raise LookupError("direct conversation not found")
    other = next(
        (member.user for member in conversation.members if member.user_id != current_user_id),
        None,
    )
    if other is None:
        raise RuntimeError("direct conversation member missing")
    profile = other.profile
    return DirectConversationResponse(
        conversation_id=conversation.id,
        other_user=ChatAuthorResponse(
            user_id=other.id,
            display_name=profile.display_name if profile else other.email.split("@", 1)[0],
            avatar_url=avatar_url_for_profile(profile) if profile else None,
        ),
    )


async def direct_conversation_member_ids(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.left_at.is_(None),
                )
            )
        ).all()
    )


async def direct_target_user_id(
    session: AsyncSession, conversation_id: uuid.UUID, current_user_id: uuid.UUID
) -> uuid.UUID:
    target = await session.scalar(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != current_user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if target is None:
        raise LookupError("direct conversation not found")
    return target


async def conversation_active_member_ids(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.left_at.is_(None),
                )
            )
        ).all()
    )


async def _validate_reply_target(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    reply_to_message_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Ensure a reply only references a message in the same room / 回覆只能引用同聊天室訊息。"""
    if reply_to_message_id is None:
        return None
    exists = await session.scalar(
        select(Message.id).where(
            Message.id == reply_to_message_id,
            Message.conversation_id == conversation_id,
        )
    )
    if exists is None:
        raise LookupError("reply target not found in conversation")
    return reply_to_message_id


async def meal_conversation_id(session: AsyncSession, meal_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(Conversation.id).where(
            Conversation.kind == "meal", Conversation.meal_event_id == meal_id
        )
    )


async def conversation_meal_id(
    session: AsyncSession, conversation_id: uuid.UUID
) -> uuid.UUID | None:
    return await session.scalar(
        select(Conversation.meal_event_id).where(Conversation.id == conversation_id)
    )


async def mark_conversation_read(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> ConversationReadResponse:
    """Advance one member's read cursor without allowing it to move backwards."""
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if conversation is None:
        raise LookupError("conversation not found")
    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if member is None:
        raise PermissionError("conversation membership required")
    if conversation.kind == "direct":
        target_id = await direct_target_user_id(session, conversation_id, user_id)
        current_blocks, target_blocks = await block_direction(session, user_id, target_id)
        if current_blocks or target_blocks:
            raise PermissionError("conversation is not available")
    elif conversation.meal_event_id is not None:
        _, can_chat = await meal_subscription_permissions(
            session, conversation.meal_event_id, user_id
        )
        if not can_chat:
            raise PermissionError("formal meal membership required")
    target_message = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
    )
    if target_message is None:
        raise LookupError("message not found")
    if member.last_read_message_id is not None:
        previous = await session.get(Message, member.last_read_message_id)
        if previous is not None and (
            target_message.created_at < previous.created_at
            or (
                target_message.created_at == previous.created_at
                and target_message.id <= previous.id
            )
        ):
            return ConversationReadResponse(
                conversation_id=conversation_id,
                meal_id=conversation.meal_event_id,
                message_id=member.last_read_message_id,
                read_at=member.last_read_at or datetime.now(UTC),
            )
    now = datetime.now(UTC)
    member.last_read_message_id = target_message.id
    member.last_read_at = now
    await session.commit()
    return ConversationReadResponse(
        conversation_id=conversation_id,
        meal_id=conversation.meal_event_id,
        message_id=target_message.id,
        read_at=now,
    )


async def unread_count(
    session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if member is None:
        return 0
    if member.last_read_message_id is None:
        return int(
            await session.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            )
            or 0
        )
    previous = await session.get(Message, member.last_read_message_id)
    if previous is None:
        return 0
    return int(
        await session.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id,
                or_(
                    Message.created_at > previous.created_at,
                    and_(
                        Message.created_at == previous.created_at,
                        Message.id > previous.id,
                    ),
                ),
            )
        )
        or 0
    )


async def recall_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> MessageResponse:
    """Recall an author's recent message while preserving its audit history."""
    message = await session.scalar(
        select(Message)
        .options(*_message_options())
        .where(Message.id == message_id, Message.conversation_id == conversation_id)
    )
    if message is None:
        raise LookupError("message not found")
    if message.sender_user_id != user_id:
        raise PermissionError("only the message author can recall it")
    if message.recalled_at is not None:
        raise ValueError("message is already recalled")
    conversation = message.conversation
    if conversation.kind == "direct":
        target_id = await direct_target_user_id(session, conversation_id, user_id)
        current_blocks, target_blocks = await block_direction(session, user_id, target_id)
        if current_blocks or target_blocks:
            raise PermissionError("conversation is not available")
    elif conversation.meal_event_id is not None:
        _, can_chat = await meal_subscription_permissions(
            session, conversation.meal_event_id, user_id
        )
        if not can_chat:
            raise PermissionError("formal meal membership required")
    if (datetime.now(UTC) - message.created_at).total_seconds() > 120:
        raise ValueError("message recall window has expired")
    message.recalled_at = datetime.now(UTC)
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    refreshed = await session.scalar(
        select(Message).options(*_message_options()).where(Message.id == message.id)
    )
    if refreshed is None:
        raise RuntimeError("recalled message could not be loaded")
    return message_response(refreshed, user_id)


async def _load_message_for_action(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> Message:
    """Load an authorized message action target / 取得已授權的訊息操作目標。"""
    if not await conversation_subscription_allowed(session, conversation_id, user_id):
        raise PermissionError("conversation is not available")
    message = await session.scalar(
        select(Message)
        .options(*_message_options())
        .where(Message.id == message_id, Message.conversation_id == conversation_id)
    )
    if message is None:
        raise LookupError("message not found")
    return message


async def pin_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> MessageResponse:
    """Pin one message in a room, idempotently / 釘選聊天室訊息且重複操作安全。"""
    message = await _load_message_for_action(session, conversation_id, user_id, message_id)
    if message.pin is None:
        # Keep the already-loaded relationship in sync before publishing the WebSocket event.
        # 先同步已載入的關聯，避免即時事件仍序列化成舊的釘選狀態。
        message.pin = MessagePin(pinned_by_user_id=user_id)
        message.conversation.updated_at = datetime.now(UTC)
        await session.commit()
    refreshed = await session.scalar(
        select(Message)
        .execution_options(populate_existing=True)
        .options(*_message_options())
        .where(Message.id == message.id)
    )
    if refreshed is None:
        raise RuntimeError("pinned message could not be loaded")
    return message_response(refreshed, user_id)


async def unpin_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> MessageResponse:
    """Remove one room pin, idempotently / 取消聊天室訊息釘選且重複操作安全。"""
    message = await _load_message_for_action(session, conversation_id, user_id, message_id)
    if message.pin is not None:
        # Assignment lets SQLAlchemy delete the orphan and clears the in-memory relationship.
        # 以關聯賦值刪除 orphan，同時清除記憶體中可能過期的釘選資料。
        message.pin = None
        message.conversation.updated_at = datetime.now(UTC)
        await session.commit()
    refreshed = await session.scalar(
        select(Message)
        .execution_options(populate_existing=True)
        .options(*_message_options())
        .where(Message.id == message.id)
    )
    if refreshed is None:
        raise RuntimeError("unpinned message could not be loaded")
    return message_response(refreshed, user_id)


async def list_pinned_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PinnedMessagesResponse:
    """List room pins in newest-pin order / 依釘選時間列出聊天室釘選。"""
    if not await conversation_subscription_allowed(session, conversation_id, user_id):
        raise PermissionError("conversation is not available")
    messages = list(
        (
            await session.scalars(
                select(Message)
                .join(MessagePin, MessagePin.message_id == Message.id)
                .options(*_message_options())
                .where(Message.conversation_id == conversation_id)
                .order_by(MessagePin.pinned_at.desc(), Message.id.desc())
            )
        ).all()
    )
    return PinnedMessagesResponse(
        messages=[message_response(message, user_id) for message in messages]
    )


async def conversation_subscription_allowed(
    session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if conversation is None:
        return False
    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if member is None:
        return False
    if conversation.kind == "direct":
        target_id = await direct_target_user_id(session, conversation_id, user_id)
        current_blocks, target_blocks = await block_direction(session, user_id, target_id)
        return not current_blocks and not target_blocks
    if conversation.meal_event_id is None:
        return False
    _, can_chat = await meal_subscription_permissions(session, conversation.meal_event_id, user_id)
    return can_chat


async def can_send_direct_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
) -> None:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == "direct",
        )
    )
    if conversation is None:
        raise LookupError("direct conversation not found")
    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == sender_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if member is None:
        raise PermissionError("conversation membership required")
    target_id = await direct_target_user_id(session, conversation_id, sender_id)
    first_blocks, second_blocks = await block_direction(session, sender_id, target_id)
    if first_blocks or second_blocks:
        raise PermissionError("direct conversation is not allowed")
    if await has_friendship(session, sender_id, target_id):
        return
    target_profile = await session.get(UserProfile, target_id)
    if target_profile is None or not target_profile.accept_stranger_messages:
        raise PermissionError("recipient does not accept stranger messages")
    sender_count = await session.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_user_id == sender_id,
        )
    )
    target_count = await session.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_user_id == target_id,
        )
    )
    if sender_count and not target_count:
        raise PermissionError("wait for a reply before sending another message")


async def create_direct_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str,
    reply_to_message_id: uuid.UUID | None = None,
) -> MessageResponse:
    normalized = content.strip()
    if not normalized:
        raise ValueError("message cannot be empty")
    if len(normalized) > 2000:
        raise ValueError("message cannot exceed 2000 characters")
    await can_send_direct_message(session, conversation_id, sender_id)
    reply_to_message_id = await _validate_reply_target(
        session, conversation_id, reply_to_message_id
    )
    message = Message(
        conversation_id=conversation_id,
        sender_user_id=sender_id,
        reply_to_message_id=reply_to_message_id,
        content=normalized,
    )
    session.add(message)
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise LookupError("direct conversation not found")
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    stored = await session.scalar(
        select(Message).options(*_message_options()).where(Message.id == message.id)
    )
    if stored is None:
        raise RuntimeError("stored message could not be loaded")
    return message_response(stored, sender_id)
