from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from api.realtime import RealtimeHub


class ClosedSocket:
    """A socket that disconnects during event fan-out / 模擬推送時已關閉的連線。"""

    async def send_json(self, payload: dict[str, Any]) -> None:
        raise WebSocketDisconnect(code=1001)


class RecordingSocket:
    """A healthy socket used to assert event delivery / 記錄健康連線收到的事件。"""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)


@pytest.mark.asyncio
async def test_disconnected_recipient_cannot_fail_pinned_event_dispatch() -> None:
    """A stale recipient is removed without undoing delivery to healthy subscribers."""
    hub = RealtimeHub()
    conversation_id = uuid4()
    stale = await hub.add(cast(WebSocket, ClosedSocket()), uuid4())
    healthy_socket = RecordingSocket()
    healthy = await hub.add(cast(WebSocket, healthy_socket), uuid4())
    stale.conversation_ids.add(conversation_id)
    healthy.conversation_ids.add(conversation_id)
    event = {
        "type": "message.pinned",
        "conversation_id": str(conversation_id),
        "message": {"id": str(uuid4()), "is_pinned": True},
    }

    await hub.dispatch(event)

    assert healthy_socket.events == [event]
    assert stale not in hub._connections
