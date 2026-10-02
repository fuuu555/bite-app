"""Friend, block and relationship policy / 好友、封鎖與關係權限規則。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import (
    Block,
    DirectConversationPair,
    FriendRequest,
    Friendship,
    User,
    UserFollow,
    UserProfile,
)
from api.domain.schemas import (
    FollowSummaryResponse,
    FriendLookupResponse,
    FriendRequestResponse,
    FriendSummaryResponse,
    RelationshipStateResponse,
    SocialActionResponse,
)
from api.services.profile import avatar_url_for_profile


def canonical_pair(first: uuid.UUID, second: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Return one stable pair key / 回傳穩定的雙使用者配對鍵。"""
    return (first, second) if first < second else (second, first)


async def user_exists(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(User.id == user_id, User.role == "user", User.is_active.is_(True))
            )
        )
    )


async def block_direction(
    session: AsyncSession, first: uuid.UUID, second: uuid.UUID
) -> tuple[bool, bool]:
    """Return (first blocks second, second blocks first) / 回傳雙向封鎖狀態。"""
    rows = await session.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(
                and_(Block.blocker_id == first, Block.blocked_id == second),
                and_(Block.blocker_id == second, Block.blocked_id == first),
            )
        )
    )
    first_blocks = False
    second_blocks = False
    for blocker_id, blocked_id in rows:
        if blocker_id == first and blocked_id == second:
            first_blocks = True
        if blocker_id == second and blocked_id == first:
            second_blocks = True
    return first_blocks, second_blocks


async def has_friendship(session: AsyncSession, first: uuid.UUID, second: uuid.UUID) -> bool:
    low, high = canonical_pair(first, second)
    return bool(
        await session.scalar(
            select(exists().where(Friendship.user_low_id == low, Friendship.user_high_id == high))
        )
    )


async def follow_flags(
    session: AsyncSession, current_user_id: uuid.UUID, target_user_id: uuid.UUID
) -> tuple[bool, bool]:
    rows = await session.execute(
        select(UserFollow.follower_id, UserFollow.followed_id).where(
            or_(
                and_(
                    UserFollow.follower_id == current_user_id,
                    UserFollow.followed_id == target_user_id,
                ),
                and_(
                    UserFollow.follower_id == target_user_id,
                    UserFollow.followed_id == current_user_id,
                ),
            )
        )
    )
    following = False
    followed_by = False
    for follower_id, followed_id in rows:
        if follower_id == current_user_id and followed_id == target_user_id:
            following = True
        if follower_id == target_user_id and followed_id == current_user_id:
            followed_by = True
    return following, followed_by


def follow_status(following: bool, followed_by: bool) -> str:
    if following and followed_by:
        return "mutual"
    if following:
        return "following"
    if followed_by:
        return "followed_by"
    return "none"


async def pending_request(
    session: AsyncSession, requester_id: uuid.UUID, recipient_id: uuid.UUID
) -> FriendRequest | None:
    return await session.scalar(
        select(FriendRequest).where(
            FriendRequest.requester_id == requester_id,
            FriendRequest.recipient_id == recipient_id,
            FriendRequest.status == "pending",
        )
    )


async def existing_direct_conversation_id(
    session: AsyncSession, first: uuid.UUID, second: uuid.UUID
) -> uuid.UUID | None:
    low, high = canonical_pair(first, second)
    return await session.scalar(
        select(DirectConversationPair.conversation_id).where(
            DirectConversationPair.user_low_id == low,
            DirectConversationPair.user_high_id == high,
        )
    )


async def relationship_state(
    session: AsyncSession, current_user_id: uuid.UUID, target_user_id: uuid.UUID
) -> RelationshipStateResponse:
    if current_user_id == target_user_id:
        return RelationshipStateResponse(status="self")

    current_blocks, target_blocks = await block_direction(session, current_user_id, target_user_id)
    if current_blocks:
        return RelationshipStateResponse(status="blocked_by_me")
    if target_blocks:
        return RelationshipStateResponse(status="blocked_me")

    following, followed_by = await follow_flags(session, current_user_id, target_user_id)
    current_follow_status = follow_status(following, followed_by)

    conversation_id = await existing_direct_conversation_id(
        session, current_user_id, target_user_id
    )
    if await has_friendship(session, current_user_id, target_user_id):
        return RelationshipStateResponse(
            status="friends",
            conversation_id=conversation_id,
            can_message=True,
            follow_status=current_follow_status,  # type: ignore[arg-type]
        )

    outgoing = await pending_request(session, current_user_id, target_user_id)
    if outgoing is not None:
        return RelationshipStateResponse(
            status="outgoing_pending",
            request_id=outgoing.id,
            conversation_id=conversation_id,
            can_message=True,
            follow_status=current_follow_status,  # type: ignore[arg-type]
        )
    incoming = await pending_request(session, target_user_id, current_user_id)
    if incoming is not None:
        return RelationshipStateResponse(
            status="incoming_pending",
            request_id=incoming.id,
            conversation_id=conversation_id,
            can_message=True,
            can_accept_friend_request=True,
            follow_status=current_follow_status,  # type: ignore[arg-type]
        )

    profile = await session.get(UserProfile, target_user_id)
    return RelationshipStateResponse(
        status="none",
        conversation_id=conversation_id,
        can_message=bool(profile and profile.accept_stranger_messages),
        can_add_friend=True,
        follow_status=current_follow_status,  # type: ignore[arg-type]
    )


def friend_request_response(request: FriendRequest) -> FriendRequestResponse:
    return FriendRequestResponse(
        id=request.id,
        requester_id=request.requester_id,
        recipient_id=request.recipient_id,
        status=request.status,  # type: ignore[arg-type]
        created_at=request.created_at,
        responded_at=request.responded_at,
    )


async def send_friend_request(
    session: AsyncSession, requester_id: uuid.UUID, recipient_id: uuid.UUID
) -> SocialActionResponse:
    if requester_id == recipient_id:
        raise ValueError("cannot add yourself")
    if not await user_exists(session, recipient_id):
        raise LookupError("user not found")
    current_blocks, target_blocks = await block_direction(session, requester_id, recipient_id)
    if current_blocks or target_blocks:
        raise PermissionError("friend request is not allowed")
    if await has_friendship(session, requester_id, recipient_id):
        raise ValueError("users are already friends")
    incoming = await pending_request(session, recipient_id, requester_id)
    if incoming is not None:
        raise ValueError("incoming friend request already exists")
    existing = await pending_request(session, requester_id, recipient_id)
    if existing is not None:
        raise ValueError("friend request already exists")
    request = FriendRequest(requester_id=requester_id, recipient_id=recipient_id)
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return SocialActionResponse(
        relationship=await relationship_state(session, requester_id, recipient_id),
        request=friend_request_response(request),
    )


async def respond_friend_request(
    session: AsyncSession,
    current_user_id: uuid.UUID,
    request_id: uuid.UUID,
    accepted: bool,
) -> SocialActionResponse:
    request = await session.scalar(
        select(FriendRequest).where(
            FriendRequest.id == request_id,
            FriendRequest.recipient_id == current_user_id,
            FriendRequest.status == "pending",
        )
    )
    if request is None:
        raise LookupError("friend request not found")
    now = datetime.now(UTC)
    request.status = "accepted" if accepted else "rejected"
    request.responded_at = now
    if accepted:
        blocked = await block_direction(session, request.requester_id, request.recipient_id)
        if any(blocked):
            raise PermissionError("friend request is not allowed")
        low, high = canonical_pair(request.requester_id, request.recipient_id)
        session.add(Friendship(user_low_id=low, user_high_id=high))
        await session.execute(
            update(FriendRequest)
            .where(
                FriendRequest.id != request.id,
                or_(
                    and_(
                        FriendRequest.requester_id == request.requester_id,
                        FriendRequest.recipient_id == request.recipient_id,
                    ),
                    and_(
                        FriendRequest.requester_id == request.recipient_id,
                        FriendRequest.recipient_id == request.requester_id,
                    ),
                ),
                FriendRequest.status == "pending",
            )
            .values(status="rejected", responded_at=now)
        )
    await session.commit()
    await session.refresh(request)
    return SocialActionResponse(
        relationship=await relationship_state(session, current_user_id, request.requester_id),
        request=friend_request_response(request),
    )


async def cancel_friend_request(
    session: AsyncSession, current_user_id: uuid.UUID, request_id: uuid.UUID
) -> SocialActionResponse:
    request = await session.scalar(
        select(FriendRequest).where(
            FriendRequest.id == request_id,
            FriendRequest.requester_id == current_user_id,
            FriendRequest.status == "pending",
        )
    )
    if request is None:
        raise LookupError("friend request not found")
    request.status = "cancelled"
    request.responded_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(request)
    return SocialActionResponse(
        relationship=await relationship_state(session, current_user_id, request.recipient_id),
        request=friend_request_response(request),
    )


async def remove_friend(
    session: AsyncSession, current_user_id: uuid.UUID, target_user_id: uuid.UUID
) -> RelationshipStateResponse:
    low, high = canonical_pair(current_user_id, target_user_id)
    result = await session.execute(
        delete(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise LookupError("friendship not found")
    await session.commit()
    return await relationship_state(session, current_user_id, target_user_id)


async def block_user(
    session: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> RelationshipStateResponse:
    if blocker_id == blocked_id:
        raise ValueError("cannot block yourself")
    if not await user_exists(session, blocked_id):
        raise LookupError("user not found")
    current_blocks, target_blocks = await block_direction(session, blocker_id, blocked_id)
    if current_blocks:
        return await relationship_state(session, blocker_id, blocked_id)
    if target_blocks:
        raise PermissionError("block action is not allowed")
    session.add(Block(blocker_id=blocker_id, blocked_id=blocked_id))
    low, high = canonical_pair(blocker_id, blocked_id)
    await session.execute(
        delete(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    await session.execute(
        delete(FriendRequest).where(
            FriendRequest.status == "pending",
            or_(
                and_(
                    FriendRequest.requester_id == blocker_id,
                    FriendRequest.recipient_id == blocked_id,
                ),
                and_(
                    FriendRequest.requester_id == blocked_id,
                    FriendRequest.recipient_id == blocker_id,
                ),
            ),
        )
    )
    await session.execute(
        delete(UserFollow).where(
            or_(
                and_(
                    UserFollow.follower_id == blocker_id,
                    UserFollow.followed_id == blocked_id,
                ),
                and_(
                    UserFollow.follower_id == blocked_id,
                    UserFollow.followed_id == blocker_id,
                ),
            )
        )
    )
    await session.commit()
    return await relationship_state(session, blocker_id, blocked_id)


async def unblock_user(
    session: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> RelationshipStateResponse:
    result = await session.execute(
        delete(Block).where(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise LookupError("block not found")
    await session.commit()
    return await relationship_state(session, blocker_id, blocked_id)


async def follow_user(
    session: AsyncSession, follower_id: uuid.UUID, followed_id: uuid.UUID
) -> RelationshipStateResponse:
    if follower_id == followed_id:
        raise ValueError("cannot follow yourself")
    if not await user_exists(session, followed_id):
        raise LookupError("user not found")
    current_blocks, target_blocks = await block_direction(session, follower_id, followed_id)
    if current_blocks or target_blocks:
        raise PermissionError("follow is not allowed")
    existing = await session.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.followed_id == followed_id,
        )
    )
    if existing is None:
        session.add(UserFollow(follower_id=follower_id, followed_id=followed_id))
        await session.commit()
    return await relationship_state(session, follower_id, followed_id)


async def unfollow_user(
    session: AsyncSession, follower_id: uuid.UUID, followed_id: uuid.UUID
) -> RelationshipStateResponse:
    result = await session.execute(
        delete(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.followed_id == followed_id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise LookupError("follow not found")
    await session.commit()
    return await relationship_state(session, follower_id, followed_id)


async def _list_follows(
    session: AsyncSession, user_id: uuid.UUID, *, following: bool
) -> list[FollowSummaryResponse]:
    relation_user_column = UserFollow.followed_id if following else UserFollow.follower_id
    rows = await session.execute(
        select(User, UserProfile, UserFollow.created_at)
        .join(UserProfile, UserProfile.user_id == relation_user_column)
        .join(User, User.id == relation_user_column)
        .options(selectinload(UserProfile.avatar_asset))
        .where(
            (UserFollow.follower_id == user_id)
            if following
            else (UserFollow.followed_id == user_id),
            User.role == "user",
            User.is_active.is_(True),
        )
        .order_by(UserFollow.created_at.desc(), relation_user_column)
    )
    return [
        FollowSummaryResponse(
            id=user.id,
            display_name=profile.display_name,
            avatar_url=avatar_url_for_profile(profile),
            avatar_source=profile.avatar_source,  # type: ignore[arg-type]
            avatar_asset_id=profile.avatar_asset_id,
            created_at=created_at,
        )
        for user, profile, created_at in rows
    ]


async def list_following(session: AsyncSession, user_id: uuid.UUID) -> list[FollowSummaryResponse]:
    return await _list_follows(session, user_id, following=True)


async def list_followers(session: AsyncSession, user_id: uuid.UUID) -> list[FollowSummaryResponse]:
    return await _list_follows(session, user_id, following=False)


async def list_pending_friend_requests(
    session: AsyncSession, user_id: uuid.UUID
) -> list[FriendRequestResponse]:
    rows = await session.scalars(
        select(FriendRequest)
        .where(
            or_(FriendRequest.requester_id == user_id, FriendRequest.recipient_id == user_id),
            FriendRequest.status == "pending",
        )
        .order_by(FriendRequest.created_at.desc(), FriendRequest.id.desc())
    )
    return [friend_request_response(request) for request in rows]


async def list_friends(session: AsyncSession, user_id: uuid.UUID) -> list[FriendSummaryResponse]:
    """List only active friends with direct conversation shortcuts / 列出有效好友與私聊入口。"""
    friendship_rows = list(
        await session.scalars(
            select(Friendship)
            .where(or_(Friendship.user_low_id == user_id, Friendship.user_high_id == user_id))
            .order_by(Friendship.created_at.desc(), Friendship.user_low_id, Friendship.user_high_id)
        )
    )
    friend_ids = [
        row.user_high_id if row.user_low_id == user_id else row.user_low_id
        for row in friendship_rows
    ]
    if not friend_ids:
        return []

    profile_rows = await session.execute(
        select(User, UserProfile)
        .join(UserProfile, UserProfile.user_id == User.id)
        .options(selectinload(UserProfile.avatar_asset))
        .where(User.id.in_(friend_ids), User.role == "user", User.is_active.is_(True))
    )
    profiles = {user.id: (user, profile) for user, profile in profile_rows}
    pair_rows = await session.execute(
        select(DirectConversationPair).where(
            or_(
                DirectConversationPair.user_low_id == user_id,
                DirectConversationPair.user_high_id == user_id,
            )
        )
    )
    conversation_ids = {
        (row.user_high_id if row.user_low_id == user_id else row.user_low_id): row.conversation_id
        for row in pair_rows.scalars()
    }

    return [
        FriendSummaryResponse(
            id=friend_id,
            display_name=profiles[friend_id][1].display_name,
            avatar_url=avatar_url_for_profile(profiles[friend_id][1]),
            avatar_source=profiles[friend_id][1].avatar_source,  # type: ignore[arg-type]
            avatar_asset_id=profiles[friend_id][1].avatar_asset_id,
            conversation_id=conversation_ids.get(friend_id),
        )
        for friend_id in friend_ids
        if friend_id in profiles
    ]


async def lookup_friend_code(
    session: AsyncSession, current_user_id: uuid.UUID, friend_code: str
) -> FriendLookupResponse:
    """Resolve one code without exposing blocked or inactive accounts / 查找單一好友碼。"""
    result = await session.execute(
        select(User, UserProfile)
        .join(UserProfile, UserProfile.user_id == User.id)
        .options(selectinload(UserProfile.avatar_asset))
        .where(
            UserProfile.friend_code == friend_code,
            User.role == "user",
            User.is_active.is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise LookupError("user not found")
    user, profile = row
    relationship = await relationship_state(session, current_user_id, user.id)
    if relationship.status in {"blocked_by_me", "blocked_me"}:
        raise LookupError("user not found")
    return FriendLookupResponse(
        id=user.id,
        display_name=profile.display_name,
        avatar_url=avatar_url_for_profile(profile),
        avatar_source=profile.avatar_source,  # type: ignore[arg-type]
        avatar_asset_id=profile.avatar_asset_id,
        conversation_id=relationship.conversation_id,
        relationship=relationship,
    )
