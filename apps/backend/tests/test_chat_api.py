"""Stage 8 meal chat and WebSocket integration tests / Stage 8 飯局聊天與即時連線測試。"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.core.database import engine, session_factory
from api.core.security import create_user_session
from api.domain.models import (
    Conversation,
    ConversationMember,
    MealEvent,
    MealMembership,
    User,
    UserProfile,
)
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS and Redis running",
)


async def _seed_chat() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str, str]:
    meal_id = uuid.uuid4()
    host_id = uuid.uuid4()
    member_id = uuid.uuid4()
    host = User(
        id=host_id,
        email=f"chat-host-{host_id.hex}@example.test",
        role="user",
        is_active=True,
    )
    member = User(
        id=member_id,
        email=f"chat-member-{member_id.hex}@example.test",
        role="user",
        is_active=True,
    )
    async with session_factory() as session:
        session.add_all(
            [
                host,
                member,
                UserProfile(user_id=host_id, display_name="聊天發起人"),
                UserProfile(user_id=member_id, display_name="聊天成員"),
            ]
        )
        await session.flush()
        _, host_token = await create_user_session(session, host, "聊天室測試")
        _, member_token = await create_user_session(session, member, "聊天室測試")
        meal = MealEvent(
            id=meal_id,
            host_user_id=host_id,
            visibility="public",
            title="即時聊天飯局",
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            join_deadline=datetime.now(UTC) + timedelta(hours=23, minutes=45),
            capacity=4,
            status="open",
        )
        conversation = Conversation(kind="meal", meal_event_id=meal_id)
        session.add_all(
            [
                meal,
                MealMembership(
                    meal_event_id=meal_id,
                    user_id=host_id,
                    membership_status="host",
                ),
                MealMembership(
                    meal_event_id=meal_id,
                    user_id=member_id,
                    membership_status="member",
                ),
                conversation,
            ]
        )
        await session.flush()
        session.add_all(
            [
                ConversationMember(conversation_id=conversation.id, user_id=host_id),
                ConversationMember(conversation_id=conversation.id, user_id=member_id),
            ]
        )
        await session.commit()
    return meal_id, host_id, member_id, host_token, member_token


async def _cleanup_chat(meal_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    async with session_factory() as session:
        await session.execute(delete(MealEvent).where(MealEvent.id == meal_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _receive_until_ack(websocket, request_id: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    while True:
        event = websocket.receive_json()
        events.append(event)
        if event.get("type") == "ack" and event.get("request_id") == request_id:
            return events


def test_meal_websocket_persists_history_and_revokes_after_leave() -> None:
    # TestClient owns another event loop; replace any pool previously used by async pytest tests.
    # TestClient 使用另一個 event loop，先換掉先前非同步測試用過的連線池。
    engine.sync_engine.dispose(close=False)
    meal_id, host_id, member_id, _, member_token = asyncio.run(_seed_chat())
    asyncio.run(engine.dispose())
    try:
        with TestClient(app) as client:
            client.cookies.set("bitemap_user_session", member_token)
            with client.websocket_connect(
                "/api/v1/ws", headers={"origin": "http://localhost:3000"}
            ) as websocket:
                assert websocket.receive_json() == {"type": "ready"}
                websocket.send_json(
                    {
                        "type": "subscribe",
                        "request_id": "chat-subscribe",
                        "meal_id": str(meal_id),
                        "channel": "chat",
                    }
                )
                subscribed = websocket.receive_json()
                assert subscribed["type"] == "subscribed"
                assert subscribed["channel"] == "chat"

                websocket.send_json(
                    {
                        "type": "message.send",
                        "request_id": "message-one",
                        "meal_id": str(meal_id),
                        "content": "  大家明天見！  ",
                    }
                )
                created = websocket.receive_json()
                acknowledged = websocket.receive_json()
                assert created["type"] == "message.created"
                assert created["message"]["content"] == "大家明天見！"
                assert "audience_user_ids" not in created
                assert acknowledged["type"] == "ack"
                assert acknowledged["request_id"] == "message-one"

                history = client.get(f"/api/v1/meals/{meal_id}/messages")
                assert history.status_code == 200
                assert [item["content"] for item in history.json()["messages"]] == ["大家明天見！"]
                conversations = client.get("/api/v1/conversations", params={"kind": "meal"})
                assert conversations.status_code == 200
                assert conversations.json()["conversations"][0]["meal_id"] == str(meal_id)

                blocked = client.post(f"/api/v1/blocks/{host_id}")
                assert blocked.status_code == 200
                websocket.send_json(
                    {
                        "type": "message.send",
                        "request_id": "message-after-block",
                        "meal_id": str(meal_id),
                        "content": "封鎖後仍可使用飯局群聊",
                    }
                )
                after_block = _receive_until_ack(websocket, "message-after-block")
                assert any(event.get("type") == "message.created" for event in after_block)

                left = client.post(f"/api/v1/meals/{meal_id}/leave")
                assert left.status_code == 200
                websocket.send_json(
                    {
                        "type": "message.send",
                        "request_id": "message-after-leave",
                        "meal_id": str(meal_id),
                        "content": "不應送出",
                    }
                )
                rejected = websocket.receive_json()
                assert rejected["type"] == "error"
                assert rejected["code"] == "forbidden"
                assert rejected["request_id"] == "message-after-leave"

                forbidden_history = client.get(f"/api/v1/meals/{meal_id}/messages")
                assert forbidden_history.status_code == 403
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(_cleanup_chat(meal_id, [host_id, member_id]))
        asyncio.run(engine.dispose())
