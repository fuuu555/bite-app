"""REST chat history and conversation-list endpoints / 聊天歷史與列表端點。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import get_session, session_factory
from api.core.security import UserSessionContext, authenticate_user_session, require_user
from api.domain.schemas import (
    ConversationListResponse,
    ConversationReadRequest,
    ConversationReadResponse,
    DirectConversationResponse,
    MessagePageResponse,
    PinnedMessagesResponse,
)
from api.realtime import RealtimeConnection, realtime
from api.services.chat import (
    conversation_active_member_ids,
    conversation_meal_id,
    conversation_subscription_allowed,
    create_direct_message,
    create_meal_message,
    delete_direct_conversation,
    direct_conversation_member_ids,
    ensure_direct_conversation,
    formal_meal_member_ids,
    list_direct_conversations,
    list_meal_conversations,
    list_pinned_messages,
    mark_conversation_read,
    meal_conversation_id,
    meal_subscription_permissions,
    pin_message,
    read_conversation_messages,
    read_meal_messages,
    recall_message,
    unpin_message,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])
logger = logging.getLogger(__name__)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UserSessionContext, Depends(require_user)]


def _chat_http_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("/meals/{meal_id}/messages", response_model=MessagePageResponse)
async def read_messages(
    meal_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePageResponse:
    try:
        return await read_meal_messages(session, meal_id, current.user.id, cursor, limit)
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePageResponse)
async def read_conversation_history(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePageResponse:
    try:
        return await read_conversation_messages(
            session, conversation_id, current.user.id, cursor, limit
        )
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.get("/meals/{meal_id}/pins", response_model=PinnedMessagesResponse)
async def read_meal_pins(
    meal_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> PinnedMessagesResponse:
    try:
        conversation_id = await meal_conversation_id(session, meal_id)
        if conversation_id is None:
            raise LookupError("meal conversation not found")
        return await list_pinned_messages(session, conversation_id, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.get("/conversations/{conversation_id}/pins", response_model=PinnedMessagesResponse)
async def read_conversation_pins(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> PinnedMessagesResponse:
    try:
        return await list_pinned_messages(session, conversation_id, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.get("/conversations", response_model=ConversationListResponse)
async def read_conversations(
    session: SessionDep,
    current: UserDep,
    kind: Annotated[Literal["meal", "direct", "friends"], Query()] = "meal",
) -> ConversationListResponse:
    if kind == "meal":
        return await list_meal_conversations(session, current.user.id)
    return await list_direct_conversations(session, current.user.id, kind)


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ConversationReadResponse,
)
async def mark_read(
    conversation_id: uuid.UUID,
    payload: ConversationReadRequest,
    session: SessionDep,
    current: UserDep,
) -> ConversationReadResponse:
    try:
        return await mark_conversation_read(
            session, conversation_id, current.user.id, payload.message_id
        )
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.post("/conversations/direct/{user_id}", response_model=DirectConversationResponse)
async def create_direct_room(
    user_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> DirectConversationResponse:
    try:
        return await ensure_direct_conversation(session, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> Response:
    try:
        member_ids = await delete_direct_conversation(session, conversation_id, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _chat_http_error(error) from error
    await realtime.publish(
        {
            "type": "conversation.deleted",
            "conversation_id": str(conversation_id),
            "audience_user_ids": [str(user_id) for user_id in member_ids],
        }
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _socket_error(
    connection: RealtimeConnection,
    request_id: str | None,
    code: str,
    message: str,
) -> None:
    await realtime.hub.send(
        connection,
        {"type": "error", "request_id": request_id, "code": code, "message": message},
    )


def _request_id(payload: dict[object, object]) -> str | None:
    value = payload.get("request_id")
    return value[:100] if isinstance(value, str) else None


def _meal_id(payload: dict[object, object]) -> uuid.UUID:
    try:
        return uuid.UUID(str(payload["meal_id"]))
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("valid meal_id required") from error


def _conversation_id(payload: dict[object, object]) -> uuid.UUID:
    try:
        return uuid.UUID(str(payload["conversation_id"]))
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("valid conversation_id required") from error


def _optional_uuid(payload: dict[object, object], key: str) -> uuid.UUID | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as error:
        raise ValueError(f"valid {key} required") from error


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket) -> None:
    """Authenticate one shared real-time connection / 驗證並處理共用即時連線。"""
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if origin not in settings.cors_origins:
        await websocket.close(code=4403, reason="origin not allowed")
        return
    async with session_factory() as session:
        current = await authenticate_user_session(
            session, websocket.cookies.get(settings.user_session_cookie)
        )
        if current is None:
            await websocket.close(code=4401, reason="authentication required")
            return
        current_user_id = current.user.id
        await websocket.accept()
        connection = await realtime.hub.add(websocket, current_user_id)
        await realtime.hub.send(connection, {"type": "ready"})
        sent_at: deque[float] = deque()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    decoded = json.loads(raw)
                    if not isinstance(decoded, dict):
                        raise ValueError("event must be an object")
                    payload: dict[object, object] = decoded
                except (json.JSONDecodeError, ValueError):
                    await _socket_error(connection, None, "invalid_event", "invalid event")
                    continue
                request_id = _request_id(payload)
                event_type = payload.get("type")
                try:
                    if event_type == "ping":
                        await realtime.hub.send(
                            connection, {"type": "pong", "request_id": request_id}
                        )
                        continue
                    if event_type in ("subscribe", "unsubscribe"):
                        channel = payload.get("channel")
                        if channel == "meal-list":
                            connection.meal_list_subscribed = event_type == "subscribe"
                            await realtime.hub.send(
                                connection,
                                {
                                    "type": (
                                        "subscribed"
                                        if event_type == "subscribe"
                                        else "unsubscribed"
                                    ),
                                    "request_id": request_id,
                                    "channel": channel,
                                },
                            )
                            continue
                        if channel == "conversation-list":
                            connection.conversation_list_subscribed = event_type == "subscribe"
                            await realtime.hub.send(
                                connection,
                                {
                                    "type": (
                                        "subscribed"
                                        if event_type == "subscribe"
                                        else "unsubscribed"
                                    ),
                                    "request_id": request_id,
                                    "channel": channel,
                                },
                            )
                            continue
                        if channel not in ("state", "chat"):
                            raise ValueError(
                                "channel must be meal-list, conversation-list, state, or chat"
                            )
                        is_conversation_chat = channel == "chat" and "conversation_id" in payload
                        if is_conversation_chat:
                            conversation_id = _conversation_id(payload)
                            target = connection.conversation_ids
                            if event_type == "subscribe":
                                if not await conversation_subscription_allowed(
                                    session, conversation_id, current_user_id
                                ):
                                    raise PermissionError("subscription not allowed")
                                target.add(conversation_id)
                            else:
                                target.discard(conversation_id)
                            await realtime.hub.send(
                                connection,
                                {
                                    "type": (
                                        "subscribed"
                                        if event_type == "subscribe"
                                        else "unsubscribed"
                                    ),
                                    "request_id": request_id,
                                    "conversation_id": str(conversation_id),
                                    "channel": channel,
                                },
                            )
                            continue
                        meal_id = _meal_id(payload)
                        if event_type == "subscribe":
                            can_view_state, can_chat = await meal_subscription_permissions(
                                session, meal_id, current_user_id
                            )
                            allowed = can_view_state if channel == "state" else can_chat
                            if not allowed:
                                raise PermissionError("subscription not allowed")
                            target = (
                                connection.state_meal_ids
                                if channel == "state"
                                else connection.chat_meal_ids
                            )
                            target.add(meal_id)
                        else:
                            target = (
                                connection.state_meal_ids
                                if channel == "state"
                                else connection.chat_meal_ids
                            )
                            target.discard(meal_id)
                        await realtime.hub.send(
                            connection,
                            {
                                "type": "subscribed"
                                if event_type == "subscribe"
                                else "unsubscribed",
                                "request_id": request_id,
                                "meal_id": str(meal_id),
                                "channel": channel,
                            },
                        )
                        continue
                    if event_type == "conversation.read":
                        conversation_id = _conversation_id(payload)
                        message_id = uuid.UUID(str(payload["message_id"]))
                        read_state = await mark_conversation_read(
                            session, conversation_id, current_user_id, message_id
                        )
                        audience = await conversation_active_member_ids(session, conversation_id)
                        await realtime.publish(
                            {
                                "type": "conversation.read",
                                "conversation_id": str(conversation_id),
                                "meal_id": (
                                    str(read_state.meal_id) if read_state.meal_id else None
                                ),
                                "message_id": str(read_state.message_id),
                                "read_at": read_state.read_at.isoformat(),
                                "user_id": str(current_user_id),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        )
                        await realtime.hub.send(
                            connection,
                            {
                                "type": "ack",
                                "request_id": request_id,
                                "conversation_id": str(conversation_id),
                                "message_id": str(read_state.message_id),
                            },
                        )
                        continue
                    if event_type in ("typing.start", "typing.stop"):
                        if "conversation_id" in payload:
                            conversation_id = _conversation_id(payload)
                        else:
                            conversation_id = await meal_conversation_id(session, _meal_id(payload))
                            if conversation_id is None:
                                raise LookupError("meal conversation not found")
                        if not await conversation_subscription_allowed(
                            session, conversation_id, current_user_id
                        ):
                            raise PermissionError("typing notification not allowed")
                        audience = await conversation_active_member_ids(session, conversation_id)
                        meal_id = await conversation_meal_id(session, conversation_id)
                        await realtime.publish(
                            {
                                "type": "typing.updated",
                                "conversation_id": str(conversation_id),
                                "meal_id": str(meal_id) if meal_id else None,
                                "user_id": str(current_user_id),
                                "display_name": current.user.email.split("@", 1)[0],
                                "is_typing": event_type == "typing.start",
                                "audience_user_ids": [
                                    str(user_id)
                                    for user_id in audience
                                    if user_id != current_user_id
                                ],
                            }
                        )
                        continue
                    if event_type == "message.recall":
                        conversation_id = _conversation_id(payload)
                        message_id = uuid.UUID(str(payload["message_id"]))
                        recalled = await recall_message(
                            session, conversation_id, current_user_id, message_id
                        )
                        audience = await conversation_active_member_ids(session, conversation_id)
                        await realtime.publish(
                            {
                                "type": "message.recalled",
                                "conversation_id": str(conversation_id),
                                "meal_id": str(recalled.meal_id) if recalled.meal_id else None,
                                "message": recalled.model_dump(mode="json"),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        )
                        await realtime.publish(
                            {
                                "type": "conversation.updated",
                                "conversation_id": str(conversation_id),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        )
                        await realtime.hub.send(
                            connection,
                            {
                                "type": "ack",
                                "request_id": request_id,
                                "message_id": str(recalled.id),
                            },
                        )
                        continue
                    if event_type in ("message.pin", "message.unpin"):
                        conversation_id = _conversation_id(payload)
                        message_id = uuid.UUID(str(payload["message_id"]))
                        audience = await conversation_active_member_ids(session, conversation_id)
                        message = (
                            await pin_message(session, conversation_id, current_user_id, message_id)
                            if event_type == "message.pin"
                            else await unpin_message(
                                session, conversation_id, current_user_id, message_id
                            )
                        )
                        await realtime.hub.send(
                            connection,
                            {
                                "type": "ack",
                                "request_id": request_id,
                                "message_id": str(message.id),
                            },
                        )
                        try:
                            # The commit is authoritative; fan-out failure must not reject it.
                            # 資料提交成功即代表操作完成，後續推送失敗不可改回失敗回覆。
                            await realtime.publish(
                                {
                                    "type": (
                                        "message.pinned"
                                        if event_type == "message.pin"
                                        else "message.unpinned"
                                    ),
                                    "conversation_id": str(conversation_id),
                                    "meal_id": str(message.meal_id) if message.meal_id else None,
                                    "message": message.model_dump(mode="json"),
                                    "audience_user_ids": [str(user_id) for user_id in audience],
                                }
                            )
                            await realtime.publish(
                                {
                                    "type": "conversation.updated",
                                    "conversation_id": str(conversation_id),
                                    "audience_user_ids": [str(user_id) for user_id in audience],
                                }
                            )
                        except Exception:
                            logger.exception(
                                "Committed message pin fan-out failed",
                                extra={
                                    "user_id": str(current_user_id),
                                    "event_type": event_type,
                                    "conversation_id": str(conversation_id),
                                    "message_id": str(message.id),
                                },
                            )
                        continue
                    if event_type == "message.send":
                        now = time.monotonic()
                        window = settings.chat_message_rate_window_seconds
                        while sent_at and sent_at[0] <= now - window:
                            sent_at.popleft()
                        if len(sent_at) >= settings.chat_message_rate_limit:
                            await _socket_error(
                                connection,
                                request_id,
                                "rate_limited",
                                "too many messages",
                            )
                            continue
                        content = payload.get("content")
                        if not isinstance(content, str):
                            raise ValueError("message content required")
                        reply_to_message_id = _optional_uuid(payload, "reply_to_message_id")
                        if "conversation_id" in payload:
                            conversation_id = _conversation_id(payload)
                            message = await create_direct_message(
                                session,
                                conversation_id,
                                current_user_id,
                                content,
                                reply_to_message_id,
                            )
                            audience = await direct_conversation_member_ids(
                                session, conversation_id
                            )
                            event = {
                                "type": "message.created",
                                "conversation_id": str(conversation_id),
                                "message": message.model_dump(mode="json"),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        else:
                            meal_id = _meal_id(payload)
                            message = await create_meal_message(
                                session,
                                meal_id,
                                current_user_id,
                                content,
                                reply_to_message_id,
                            )
                            audience = await formal_meal_member_ids(session, meal_id)
                            event = {
                                "type": "message.created",
                                "meal_id": str(meal_id),
                                "conversation_id": str(message.conversation_id),
                                "message": message.model_dump(mode="json"),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        sent_at.append(now)
                        await realtime.publish(event)
                        await realtime.publish(
                            {
                                "type": "conversation.updated",
                                "conversation_id": str(message.conversation_id),
                                "audience_user_ids": [str(user_id) for user_id in audience],
                            }
                        )
                        await realtime.hub.send(
                            connection,
                            {
                                "type": "ack",
                                "request_id": request_id,
                                "message_id": str(message.id),
                            },
                        )
                        continue
                    raise ValueError("unknown event type")
                except PermissionError as error:
                    await session.rollback()
                    await _socket_error(connection, request_id, "forbidden", str(error))
                except (KeyError, ValueError, LookupError) as error:
                    await session.rollback()
                    await _socket_error(connection, request_id, "invalid_request", str(error))
                except Exception:
                    await session.rollback()
                    logger.exception(
                        "WebSocket event processing failed",
                        extra={"user_id": str(current_user_id), "event_type": event_type},
                    )
                    await _socket_error(
                        connection,
                        request_id,
                        "server_error",
                        "event could not be processed",
                    )
        except WebSocketDisconnect:
            pass
        finally:
            await realtime.hub.remove(connection)
