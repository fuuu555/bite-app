"""Friend and direct-chat integration tests / 好友與私訊整合測試。"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from api.core.database import engine, session_factory
from api.core.security import create_user_session
from api.domain.models import Conversation, ConversationMember, Message, User, UserProfile
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS and Redis running",
)


async def _seed_social_users() -> tuple[list[uuid.UUID], list[str]]:
    user_ids = [uuid.uuid4() for _ in range(3)]
    users = [
        User(id=user_id, email=f"social-{user_id.hex}@example.test", role="user", is_active=True)
        for user_id in user_ids
    ]
    async with session_factory() as session:
        session.add_all(users)
        session.add_all(
            [
                UserProfile(user_id=user_ids[0], display_name="私訊甲"),
                UserProfile(user_id=user_ids[1], display_name="私訊乙"),
                UserProfile(user_id=user_ids[2], display_name="私訊丙"),
            ]
        )
        await session.flush()
        tokens = [(await create_user_session(session, user, "社交測試"))[1] for user in users]
        await session.commit()
    return user_ids, tokens


async def _cleanup_social_users(user_ids: list[uuid.UUID]) -> None:
    async with session_factory() as session:
        await session.execute(delete(Message).where(Message.sender_user_id.in_(user_ids)))
        conversation_ids = select(ConversationMember.conversation_id).where(
            ConversationMember.user_id.in_(user_ids)
        )
        await session.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _receive_until_ack(websocket, request_id: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    while True:
        event = websocket.receive_json()
        events.append(event)
        if event.get("type") == "ack" and event.get("request_id") == request_id:
            return events


def _receive_until_type(websocket, event_type: str) -> dict[str, object]:
    while True:
        event = websocket.receive_json()
        if event.get("type") == event_type:
            return event


def test_direct_chat_policy_friend_reuse_and_block() -> None:
    engine.sync_engine.dispose(close=False)
    user_ids, tokens = asyncio.run(_seed_social_users())
    asyncio.run(engine.dispose())
    try:
        with TestClient(app) as client:
            client.cookies.set("bitemap_user_session", tokens[0])

            room = client.post(f"/api/v1/conversations/direct/{user_ids[1]}")
            assert room.status_code == 200
            conversation_id = room.json()["conversation_id"]

            profile = client.get("/api/v1/me/profile")
            assert profile.status_code == 200
            friend_code = profile.json()["friend_code"]
            assert len(friend_code) == 6 and friend_code.isascii() and friend_code.isdigit()
            self_lookup = client.get("/api/v1/users/lookup", params={"friend_code": friend_code})
            assert self_lookup.status_code == 200
            assert self_lookup.json()["relationship"]["status"] == "self"
            assert "friend_code" not in client.get(f"/api/v1/profiles/{user_ids[1]}").json()

            client.cookies.set("bitemap_user_session", tokens[1])
            settings = client.patch(
                "/api/v1/me/profile",
                json={"accept_stranger_messages": False},
            )
            assert settings.status_code == 200

            client.cookies.set("bitemap_user_session", tokens[0])
            with client.websocket_connect(
                "/api/v1/ws", headers={"origin": "http://localhost:3000"}
            ) as sender_ws:
                client.cookies.set("bitemap_user_session", tokens[1])
                with client.websocket_connect(
                    "/api/v1/ws", headers={"origin": "http://localhost:3000"}
                ) as recipient_ws:
                    assert sender_ws.receive_json() == {"type": "ready"}
                    assert recipient_ws.receive_json() == {"type": "ready"}
                    for websocket in (sender_ws, recipient_ws):
                        websocket.send_json(
                            {
                                "type": "subscribe",
                                "request_id": "subscribe",
                                "channel": "chat",
                                "conversation_id": conversation_id,
                            }
                        )
                        subscribed = websocket.receive_json()
                        assert subscribed["type"] == "subscribed", subscribed

                    sender_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "blocked-first",
                            "conversation_id": conversation_id,
                            "content": "不應該送出",
                        }
                    )
                    blocked = sender_ws.receive_json()
                    assert blocked["type"] == "error"
                    assert blocked["code"] == "forbidden"

                    client.cookies.set("bitemap_user_session", tokens[1])
                    settings = client.patch(
                        "/api/v1/me/profile",
                        json={"accept_stranger_messages": True},
                    )
                    assert settings.status_code == 200
                    sender_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "first",
                            "conversation_id": conversation_id,
                            "content": "你好，我是甲",
                        }
                    )
                    sender_events = _receive_until_ack(sender_ws, "first")
                    assert any(event.get("type") == "message.created" for event in sender_events)

                    sender_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "second-too-soon",
                            "conversation_id": conversation_id,
                            "content": "第二句",
                        }
                    )
                    too_soon = sender_ws.receive_json()
                    assert too_soon["type"] == "error"
                    assert too_soon["code"] == "forbidden"

                    recipient_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "reply",
                            "conversation_id": conversation_id,
                            "content": "你好，乙收到",
                        }
                    )
                    reply_events = _receive_until_ack(recipient_ws, "reply")
                    assert any(event.get("type") == "message.created" for event in reply_events)

                    sender_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "second-after-reply",
                            "conversation_id": conversation_id,
                            "content": "那就約下次吃飯",
                        }
                    )
                    _receive_until_ack(sender_ws, "second-after-reply")
                    _receive_until_type(recipient_ws, "message.created")
                    history = client.get(f"/api/v1/conversations/{conversation_id}/messages")
                    sender_message_id = history.json()["messages"][-1]["id"]

                    sender_ws.send_json(
                        {
                            "type": "message.pin",
                            "request_id": "pin-latest",
                            "conversation_id": conversation_id,
                            "message_id": sender_message_id,
                        }
                    )
                    _receive_until_ack(sender_ws, "pin-latest")
                    pin_event = _receive_until_type(sender_ws, "message.pinned")
                    pin_payload = pin_event.get("message")
                    assert isinstance(pin_payload, dict)
                    assert pin_payload.get("is_pinned") is True
                    assert pin_payload.get("pinned_at") is not None
                    pins = client.get(f"/api/v1/conversations/{conversation_id}/pins")
                    assert pins.status_code == 200
                    assert pins.json()["messages"][0]["id"] == sender_message_id

                    recipient_ws.send_json(
                        {
                            "type": "message.send",
                            "request_id": "reply-to-message",
                            "conversation_id": conversation_id,
                            "content": "回覆上一句",
                            "reply_to_message_id": sender_message_id,
                        }
                    )
                    reply_to_events = _receive_until_ack(recipient_ws, "reply-to-message")
                    assert any(event.get("type") == "message.created" for event in reply_to_events)
                    reply_history = client.get(f"/api/v1/conversations/{conversation_id}/messages")
                    reply_message = next(
                        item
                        for item in reply_history.json()["messages"]
                        if item["content"] == "回覆上一句"
                    )
                    assert reply_message["reply_to"]["id"] == sender_message_id

                    sender_ws.send_json(
                        {
                            "type": "message.unpin",
                            "request_id": "unpin-latest",
                            "conversation_id": conversation_id,
                            "message_id": sender_message_id,
                        }
                    )
                    _receive_until_ack(sender_ws, "unpin-latest")
                    unpin_event = _receive_until_type(sender_ws, "message.unpinned")
                    unpin_payload = unpin_event.get("message")
                    assert isinstance(unpin_payload, dict)
                    assert unpin_payload.get("is_pinned") is False
                    assert unpin_payload.get("pinned_at") is None

                    sender_ws.send_json(
                        {
                            "type": "typing.start",
                            "conversation_id": conversation_id,
                        }
                    )
                    typing = _receive_until_type(recipient_ws, "typing.updated")
                    assert typing["type"] == "typing.updated"
                    assert typing["is_typing"] is True
                    sender_ws.send_json(
                        {
                            "type": "typing.stop",
                            "conversation_id": conversation_id,
                        }
                    )
                    stopped = _receive_until_type(recipient_ws, "typing.updated")
                    assert stopped["type"] == "typing.updated"
                    assert stopped["is_typing"] is False

                    recipient_ws.send_json(
                        {
                            "type": "conversation.read",
                            "request_id": "read-latest",
                            "conversation_id": conversation_id,
                            "message_id": sender_message_id,
                        }
                    )
                    _receive_until_ack(recipient_ws, "read-latest")

                    sender_ws.send_json(
                        {
                            "type": "message.recall",
                            "request_id": "recall-latest",
                            "conversation_id": conversation_id,
                            "message_id": sender_message_id,
                        }
                    )
                    recalled_events = _receive_until_ack(sender_ws, "recall-latest")
                    assert any(event.get("type") == "message.recalled" for event in recalled_events)
                    recalled_history = client.get(
                        f"/api/v1/conversations/{conversation_id}/messages"
                    )
                    recalled_message = next(
                        item
                        for item in recalled_history.json()["messages"]
                        if item["id"] == sender_message_id
                    )
                    assert recalled_message["is_recalled"] is True
                    assert recalled_message["content"] == ""

            client.cookies.set("bitemap_user_session", tokens[0])
            recipient_profile = client.get("/api/v1/profiles/" + str(user_ids[1]))
            recipient_code = recipient_profile.json().get("friend_code")
            assert recipient_code is None
            # Lookup uses the recipient's private code obtained from a second authenticated session.
            client.cookies.set("bitemap_user_session", tokens[1])
            recipient_code = client.get("/api/v1/me/profile").json()["friend_code"]
            client.cookies.set("bitemap_user_session", tokens[0])
            lookup = client.get("/api/v1/users/lookup", params={"friend_code": recipient_code})
            assert lookup.status_code == 200
            assert lookup.json()["id"] == str(user_ids[1])
            request = client.post("/api/v1/friend-requests", json={"user_id": str(user_ids[1])})
            assert request.status_code == 201
            request_id = request.json()["request"]["id"]
            client.cookies.set("bitemap_user_session", tokens[1])
            accepted = client.post(f"/api/v1/friend-requests/{request_id}/accept")
            assert accepted.status_code == 200
            client.cookies.set("bitemap_user_session", tokens[0])
            followed = client.post(f"/api/v1/users/{user_ids[1]}/follow")
            assert followed.status_code == 200
            assert followed.json()["follow_status"] == "following"
            following = client.get("/api/v1/me/following")
            assert following.status_code == 200
            assert following.json()[0]["id"] == str(user_ids[1])
            client.cookies.set("bitemap_user_session", tokens[1])
            followers = client.get("/api/v1/me/followers")
            assert followers.status_code == 200
            assert followers.json()[0]["id"] == str(user_ids[0])
            client.cookies.set("bitemap_user_session", tokens[0])
            friends = client.get("/api/v1/conversations", params={"kind": "friends"})
            assert friends.status_code == 200
            assert friends.json()["conversations"][0]["conversation_id"] == conversation_id
            friend_list = client.get("/api/v1/friends")
            assert friend_list.status_code == 200
            assert friend_list.json()[0]["id"] == str(user_ids[1])
            assert friend_list.json()[0]["conversation_id"] == conversation_id

            blocked = client.post(f"/api/v1/blocks/{user_ids[1]}")
            assert blocked.status_code == 200
            assert blocked.json()["status"] == "blocked_by_me"
            assert client.get("/api/v1/me/following").json() == []
            client.cookies.set("bitemap_user_session", tokens[1])
            rejected_room = client.post(f"/api/v1/conversations/direct/{user_ids[0]}")
            assert rejected_room.status_code == 403
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(_cleanup_social_users(user_ids))
        asyncio.run(engine.dispose())
