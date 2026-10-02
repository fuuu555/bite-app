"""Local WebSocket fan-out with Redis cross-instance transport / 本機推送與 Redis 跨程序事件。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from redis.exceptions import RedisError

from api.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class RealtimeConnection:
    """One authenticated socket and its authorized subscriptions / 單一驗證連線與訂閱。"""

    websocket: WebSocket
    user_id: uuid.UUID
    state_meal_ids: set[uuid.UUID] = field(default_factory=set)
    chat_meal_ids: set[uuid.UUID] = field(default_factory=set)
    conversation_ids: set[uuid.UUID] = field(default_factory=set)
    meal_list_subscribed: bool = False
    conversation_list_subscribed: bool = False
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RealtimeHub:
    def __init__(self) -> None:
        self._connections: set[RealtimeConnection] = set()
        self._lock = asyncio.Lock()

    async def add(self, websocket: WebSocket, user_id: uuid.UUID) -> RealtimeConnection:
        connection = RealtimeConnection(websocket=websocket, user_id=user_id)
        async with self._lock:
            self._connections.add(connection)
        return connection

    async def remove(self, connection: RealtimeConnection) -> None:
        async with self._lock:
            self._connections.discard(connection)

    async def send(self, connection: RealtimeConnection, payload: dict[str, Any]) -> None:
        async with connection.send_lock:
            await connection.websocket.send_json(payload)

    async def dispatch(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        # Audience and source fields are transport metadata, never part of the browser contract.
        # 受眾與來源欄位只供伺服器路由使用，不屬於瀏覽器事件合約。
        client_event = {
            key: value
            for key, value in event.items()
            if key not in {"audience_user_ids", "source_id"}
        }
        if event_type == "meal.list.updated":
            async with self._lock:
                connections = [
                    connection
                    for connection in self._connections
                    if connection.meal_list_subscribed
                ]
            for connection in connections:
                try:
                    await self.send(connection, client_event)
                except (RuntimeError, OSError, WebSocketDisconnect):
                    await self.remove(connection)
            return
        if event_type == "social.updated":
            await self._dispatch_to_audience(client_event, event.get("audience_user_ids"))
            return
        if event_type in {"conversation.updated", "conversation.deleted"}:
            raw_conversation_id = event.get("conversation_id")
            try:
                conversation_id = uuid.UUID(str(raw_conversation_id))
            except (ValueError, TypeError):
                logger.warning("Ignoring realtime event with invalid conversation id")
                return
            raw_audience = event.get("audience_user_ids")
            try:
                audience = (
                    {uuid.UUID(value) for value in raw_audience}
                    if raw_audience is not None
                    else None
                )
            except (TypeError, ValueError):
                logger.warning("Ignoring conversation event with invalid audience")
                return
            async with self._lock:
                connections = [
                    connection
                    for connection in self._connections
                    if connection.conversation_list_subscribed
                    or conversation_id in connection.conversation_ids
                ]
            if audience is not None:
                connections = [
                    connection for connection in connections if connection.user_id in audience
                ]
            await self._send_many(connections, client_event)
            return
        try:
            meal_id = uuid.UUID(str(event["meal_id"]))
        except (KeyError, ValueError, TypeError):
            meal_id = None
        conversation_id: uuid.UUID | None = None
        if (
            event_type
            in {
                "message.created",
                "message.recalled",
                "message.pinned",
                "message.unpinned",
                "conversation.read",
                "typing.updated",
            }
            and event.get("conversation_id") is not None
        ):
            try:
                conversation_id = uuid.UUID(str(event["conversation_id"]))
            except (ValueError, TypeError):
                logger.warning("Ignoring realtime event with invalid conversation id")
                return
        if meal_id is None and conversation_id is None:
            logger.warning("Ignoring realtime event without a target", extra={"event": event_type})
            return
        raw_audience = event.get("audience_user_ids")
        try:
            audience = (
                {uuid.UUID(value) for value in raw_audience} if raw_audience is not None else None
            )
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring realtime event with invalid audience", extra={"event": event_type}
            )
            return
        async with self._lock:
            connections = list(self._connections)
        stale: list[RealtimeConnection] = []
        for connection in connections:
            if event_type in {
                "message.created",
                "message.recalled",
                "message.pinned",
                "message.unpinned",
                "conversation.read",
                "typing.updated",
            }:
                subscribed = (meal_id is not None and meal_id in connection.chat_meal_ids) or (
                    conversation_id is not None and conversation_id in connection.conversation_ids
                )
            else:
                subscribed = meal_id is not None and meal_id in connection.state_meal_ids
            if not subscribed or (audience is not None and connection.user_id not in audience):
                continue
            try:
                await self.send(connection, client_event)
            except (RuntimeError, OSError, WebSocketDisconnect):
                stale.append(connection)
        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)

    async def _dispatch_to_audience(self, event: dict[str, Any], raw_audience: Any) -> None:
        try:
            audience = {uuid.UUID(value) for value in raw_audience or []}
        except (TypeError, ValueError):
            logger.warning("Ignoring realtime event with invalid audience")
            return
        async with self._lock:
            connections = [
                connection for connection in self._connections if connection.user_id in audience
            ]
        await self._send_many(connections, event)

    async def _send_many(
        self, connections: list[RealtimeConnection], event: dict[str, Any]
    ) -> None:
        stale: list[RealtimeConnection] = []
        for connection in connections:
            try:
                await self.send(connection, event)
            except (RuntimeError, OSError, WebSocketDisconnect):
                stale.append(connection)
        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)


class RealtimeService:
    """Publish locally first, then bridge the same event through Redis / 先本機推送再跨 Redis。"""

    def __init__(self) -> None:
        self.hub = RealtimeHub()
        self._source_id = uuid.uuid4().hex
        self._redis: Redis | None = None
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        settings = get_settings()
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=5,
        )
        self._listener_task = asyncio.create_task(self._listen(), name="bitemap-redis-realtime")

    async def stop(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)
            self._listener_task = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def publish(self, event: dict[str, Any]) -> None:
        await self.hub.dispatch(event)
        if self._redis is None:
            return
        envelope = {**event, "source_id": self._source_id}
        try:
            await self._redis.publish(get_settings().realtime_channel, json.dumps(envelope))
        except RedisError:
            # PostgreSQL remains authoritative; reconnecting clients recover through REST.
            # PostgreSQL 仍是權威來源，客戶端重連後會透過 REST 補齊。
            logger.warning("Redis realtime publish failed", exc_info=True)

    async def _listen(self) -> None:
        retry_seconds = 1.0
        while True:
            try:
                if self._redis is None:
                    return
                async with self._redis.pubsub() as pubsub:
                    await pubsub.subscribe(get_settings().realtime_channel)
                    retry_seconds = 1.0
                    while True:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1
                        )
                        if message is None:
                            await asyncio.sleep(0)
                            continue
                        event = json.loads(message["data"])
                        if event.get("source_id") != self._source_id:
                            event.pop("source_id", None)
                            await self.hub.dispatch(event)
            except asyncio.CancelledError:
                raise
            except (RedisError, json.JSONDecodeError, TypeError):
                logger.warning("Redis realtime listener disconnected", exc_info=True)
                await asyncio.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 30.0)


realtime = RealtimeService()
