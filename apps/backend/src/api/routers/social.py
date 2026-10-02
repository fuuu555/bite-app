"""Friend and block relationship endpoints / 好友與封鎖關係端點。"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import UserSessionContext, require_user
from api.domain.schemas import (
    FollowSummaryResponse,
    FriendLookupResponse,
    FriendRequestCreateRequest,
    FriendRequestResponse,
    FriendSummaryResponse,
    RelationshipStateResponse,
    SocialActionResponse,
)
from api.realtime import realtime
from api.services.social import (
    block_user,
    cancel_friend_request,
    existing_direct_conversation_id,
    follow_user,
    list_followers,
    list_following,
    list_friends,
    list_pending_friend_requests,
    lookup_friend_code,
    remove_friend,
    respond_friend_request,
    send_friend_request,
    unblock_user,
    unfollow_user,
)

router = APIRouter(prefix="/api/v1", tags=["social"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UserSessionContext, Depends(require_user)]

_friend_code_lookup_history: dict[uuid.UUID, deque[float]] = defaultdict(deque)
_FRIEND_CODE_LOOKUP_LIMIT = 30
_FRIEND_CODE_LOOKUP_WINDOW_SECONDS = 60.0


def _allow_friend_code_lookup(user_id: uuid.UUID) -> bool:
    """Bound repeated code enumeration per session user / 限制單一使用者的好友碼枚舉。"""
    now = time.monotonic()
    history = _friend_code_lookup_history[user_id]
    while history and history[0] <= now - _FRIEND_CODE_LOOKUP_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= _FRIEND_CODE_LOOKUP_LIMIT:
        return False
    history.append(now)
    return True


def _social_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


async def _publish_social(
    *user_ids: uuid.UUID,
    action: Literal["friend_created", "friend_removed", "user_blocked", "blocked_by_user"]
    | None = None,
    conversation_id: uuid.UUID | None = None,
) -> None:
    """Publish social invalidation with an optional, non-authoritative UI hint.

    發送社交資料失效事件；提示欄位只供前端顯示，關係與聊天室仍以 REST 重抓為準。
    """
    payload: dict[str, object] = {
        "type": "social.updated",
        "audience_user_ids": [str(user_id) for user_id in set(user_ids)],
    }
    if action is not None:
        payload["action"] = action
    if conversation_id is not None:
        payload["conversation_id"] = str(conversation_id)
    await realtime.publish(payload)


@router.get("/friend-requests", response_model=list[FriendRequestResponse])
async def read_friend_requests(
    session: SessionDep, current: UserDep
) -> list[FriendRequestResponse]:
    return await list_pending_friend_requests(session, current.user.id)


@router.get("/friends", response_model=list[FriendSummaryResponse])
async def read_friends(session: SessionDep, current: UserDep) -> list[FriendSummaryResponse]:
    return await list_friends(session, current.user.id)


@router.get("/me/following", response_model=list[FollowSummaryResponse])
async def read_following(session: SessionDep, current: UserDep) -> list[FollowSummaryResponse]:
    return await list_following(session, current.user.id)


@router.get("/me/followers", response_model=list[FollowSummaryResponse])
async def read_followers(session: SessionDep, current: UserDep) -> list[FollowSummaryResponse]:
    return await list_followers(session, current.user.id)


@router.get("/users/lookup", response_model=FriendLookupResponse)
async def lookup_user_by_friend_code(
    friend_code: Annotated[str, Query(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")],
    session: SessionDep,
    current: UserDep,
) -> FriendLookupResponse:
    if not _allow_friend_code_lookup(current.user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many friend code lookups",
        )
    try:
        return await lookup_friend_code(session, current.user.id, friend_code)
    except (LookupError, PermissionError, ValueError) as error:
        raise _social_error(error) from error


@router.post("/friend-requests", response_model=SocialActionResponse, status_code=201)
async def create_friend_request(
    payload: FriendRequestCreateRequest,
    session: SessionDep,
    current: UserDep,
) -> SocialActionResponse:
    try:
        response = await send_friend_request(session, current.user.id, payload.user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(current.user.id, payload.user_id)
    return response


@router.post(
    "/friend-requests/{request_id}/accept",
    response_model=SocialActionResponse,
)
async def accept_friend_request(
    request_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> SocialActionResponse:
    try:
        response = await respond_friend_request(session, current.user.id, request_id, True)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    if response.request is not None:
        await _publish_social(
            current.user.id,
            response.request.requester_id,
            action="friend_created",
            conversation_id=response.relationship.conversation_id,
        )
    return response


@router.post(
    "/friend-requests/{request_id}/reject",
    response_model=SocialActionResponse,
)
async def reject_friend_request(
    request_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> SocialActionResponse:
    try:
        response = await respond_friend_request(session, current.user.id, request_id, False)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    if response.request is not None:
        await _publish_social(current.user.id, response.request.requester_id)
    return response


@router.post(
    "/friend-requests/{request_id}/cancel",
    response_model=SocialActionResponse,
)
async def cancel_request(
    request_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> SocialActionResponse:
    try:
        response = await cancel_friend_request(session, current.user.id, request_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    if response.request is not None:
        await _publish_social(current.user.id, response.request.recipient_id)
    return response


@router.delete("/friends/{user_id}", response_model=RelationshipStateResponse)
async def delete_friend(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> RelationshipStateResponse:
    try:
        response = await remove_friend(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(
        current.user.id,
        user_id,
        action="friend_removed",
        conversation_id=response.conversation_id,
    )
    return response


@router.post("/users/{user_id}/follow", response_model=RelationshipStateResponse)
async def create_follow(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> RelationshipStateResponse:
    try:
        response = await follow_user(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(current.user.id, user_id)
    return response


@router.delete("/users/{user_id}/follow", response_model=RelationshipStateResponse)
async def delete_follow(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> RelationshipStateResponse:
    try:
        response = await unfollow_user(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(current.user.id, user_id)
    return response


@router.post("/blocks/{user_id}", response_model=RelationshipStateResponse)
async def create_block(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> RelationshipStateResponse:
    conversation_id = await existing_direct_conversation_id(session, current.user.id, user_id)
    try:
        response = await block_user(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(
        current.user.id,
        action="user_blocked",
        conversation_id=conversation_id,
    )
    await _publish_social(
        user_id,
        action="blocked_by_user",
        conversation_id=conversation_id,
    )
    return response


@router.delete("/blocks/{user_id}", response_model=RelationshipStateResponse)
async def delete_block(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> RelationshipStateResponse:
    try:
        response = await unblock_user(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _social_error(error) from error
    await _publish_social(current.user.id, user_id)
    return response
