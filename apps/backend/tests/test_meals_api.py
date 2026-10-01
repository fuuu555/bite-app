"""Meal membership and voting integration tests / 約飯成員與投票整合測試。"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.database import session_factory
from api.core.security import create_user_session
from api.domain.models import Cuisine, MealCandidate, MealEvent, Restaurant, User, UserProfile
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


@pytest.mark.asyncio
async def test_public_meal_vote_and_private_application() -> None:
    unique = uuid.uuid4().hex
    cuisine_id = uuid.uuid4()
    first_restaurant_id = uuid.uuid4()
    second_restaurant_id = uuid.uuid4()
    host_id = uuid.uuid4()
    guest_id = uuid.uuid4()
    host_token: str | None = None
    guest_token: str | None = None
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Cuisine(
                id=cuisine_id,
                slug=f"meal-{unique}",
                display_name="約飯測試料理",
                color="#F26B4F",
                icon_key="bowl",
                is_active=True,
            )
        )
        session.add_all(
            [
                Restaurant(
                    id=first_restaurant_id,
                    name="約飯測試餐廳一號",
                    address="桃園市中壢區測試路 7 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="200_to_400",
                    status="published",
                    source_type="manual",
                ),
                Restaurant(
                    id=second_restaurant_id,
                    name="約飯測試餐廳二號",
                    address="桃園市中壢區測試路 8 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="200_to_400",
                    status="published",
                    source_type="manual",
                ),
            ]
        )
        host = User(
            id=host_id,
            email=f"meal-host-{unique}@example.test",
            password_hash=None,
            role="user",
            is_active=True,
        )
        guest = User(
            id=guest_id,
            email=f"meal-guest-{unique}@example.test",
            password_hash=None,
            role="user",
            is_active=True,
        )
        session.add_all(
            [
                host,
                guest,
                UserProfile(user_id=host_id, display_name="約飯發起人"),
                UserProfile(user_id=guest_id, display_name="約飯申請者"),
            ]
        )
        await session.flush()
        _, host_token = await create_user_session(session, host, "約飯發起人瀏覽器")
        _, guest_token = await create_user_session(session, guest, "約飯申請者瀏覽器")

    try:
        async with (
            AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            ) as host_client,
            AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            ) as guest_client,
        ):
            host_client.cookies.set("bitemap_user_session", host_token)
            guest_client.cookies.set("bitemap_user_session", guest_token)

            created = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "public",
                    "title": "公開投票飯局",
                    "description": "一起選晚餐",
                    "scheduled_at": (now + timedelta(minutes=28)).isoformat(),
                    "join_deadline": (now + timedelta(minutes=13)).isoformat(),
                    "capacity": 3,
                    "restaurant_mode": "vote",
                    "restaurant_id": str(first_restaurant_id),
                },
            )
            assert created.status_code == 201
            public_meal = created.json()
            meal_id = public_meal["id"]
            assert public_meal["member_count"] == 1
            assert len(public_meal["candidates"]) == 1
            assert public_meal["candidates"][0]["vote_count"] is None

            added_candidate = await host_client.post(
                f"/api/v1/meals/{meal_id}/candidates",
                json={"restaurant_id": str(second_restaurant_id)},
            )
            assert added_candidate.status_code == 200
            assert len(added_candidate.json()["candidates"]) == 2

            public_listing = await guest_client.get("/api/v1/meals", params={"scope": "public"})
            assert public_listing.status_code == 200
            listed_meal = next(
                item for item in public_listing.json()["meals"] if item["id"] == meal_id
            )
            assert all(candidate["vote_count"] is None for candidate in listed_meal["candidates"])

            joined = await guest_client.post(f"/api/v1/meals/{meal_id}/join")
            assert joined.status_code == 200
            assert joined.json()["my_membership_status"] == "member"

            guest_left = await guest_client.post(f"/api/v1/meals/{meal_id}/leave")
            assert guest_left.status_code == 200
            assert guest_left.json()["my_membership_status"] == "left"
            assert guest_left.json()["member_count"] == 1

            rejoined = await guest_client.post(f"/api/v1/meals/{meal_id}/join")
            assert rejoined.status_code == 200
            assert rejoined.json()["my_membership_status"] == "member"

            non_host_cancel = await guest_client.post(f"/api/v1/meals/{meal_id}/cancel")
            assert non_host_cancel.status_code == 403

            voting = await host_client.post(f"/api/v1/meals/{meal_id}/start-voting")
            assert voting.status_code == 200
            candidate_id = voting.json()["candidates"][0]["id"]
            assert voting.json()["status"] == "voting"
            assert all(
                isinstance(candidate["vote_count"], int)
                for candidate in voting.json()["candidates"]
            )

            guest_vote = await guest_client.post(
                f"/api/v1/meals/{meal_id}/votes", json={"candidate_id": candidate_id}
            )
            assert guest_vote.status_code == 200
            assert guest_vote.json()["candidates"][0]["vote_count"] == 1

            # Ballots are unique per member, not per candidate: many members may choose one place.
            # 選票以成員為唯一單位，不限制候選餐廳；不同成員可投給同一家並累加票數。
            host_vote = await host_client.post(
                f"/api/v1/meals/{meal_id}/votes", json={"candidate_id": candidate_id}
            )
            assert host_vote.status_code == 200
            assert host_vote.json()["candidates"][0]["vote_count"] == 2

            removed = await host_client.post(f"/api/v1/meals/{meal_id}/members/{guest_id}/remove")
            assert removed.status_code == 200
            assert removed.json()["member_count"] == 1
            assert removed.json()["candidates"][0]["vote_count"] == 1
            removed_member_view = await guest_client.get(f"/api/v1/meals/{meal_id}")
            assert removed_member_view.status_code == 200
            assert all(
                candidate["vote_count"] is None
                for candidate in removed_member_view.json()["candidates"]
            )
            revoked_vote = await guest_client.post(
                f"/api/v1/meals/{meal_id}/votes", json={"candidate_id": candidate_id}
            )
            assert revoked_vote.status_code == 403

            decided = await host_client.post(f"/api/v1/meals/{meal_id}/finalize-vote")
            assert decided.status_code == 200
            assert decided.json()["status"] == "decided"
            assert decided.json()["decided_restaurant"]["id"] == str(first_restaurant_id)
            decided_cancel = await host_client.post(f"/api/v1/meals/{meal_id}/cancel")
            assert decided_cancel.status_code == 200
            assert decided_cancel.json()["status"] == "cancelled"
            cancelled_guest_view = await guest_client.get(f"/api/v1/meals/{meal_id}")
            assert cancelled_guest_view.status_code == 410
            assert cancelled_guest_view.json()["detail"] == "meal cancelled"

            private_created = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "private",
                    "title": "審核制飯局",
                    "description": None,
                    "scheduled_at": (now + timedelta(days=3)).isoformat(),
                    "join_deadline": None,
                    "capacity": 2,
                    "restaurant_mode": "direct",
                    "restaurant_id": str(second_restaurant_id),
                },
            )
            assert private_created.status_code == 201
            private_meal_id = private_created.json()["id"]

            # Seed a candidate defensively: private voting is currently disabled, but the response
            # must remain fail-closed if legacy or future data contains candidates.
            # 防禦性建立候選資料，確認私人申請者未核准前 API 不會洩漏候選內容。
            async with session_factory() as session:
                session.add(
                    MealCandidate(
                        meal_event_id=uuid.UUID(private_meal_id),
                        restaurant_id=first_restaurant_id,
                        position=1,
                    )
                )
                await session.commit()

            private_before_application = await guest_client.get(f"/api/v1/meals/{private_meal_id}")
            assert private_before_application.status_code == 200
            assert private_before_application.json()["candidates"] == []
            assert private_before_application.json()["can_join"] is True

            applied = await guest_client.post(f"/api/v1/meals/{private_meal_id}/join")
            assert applied.status_code == 200
            assert applied.json()["my_membership_status"] == "pending"
            assert applied.json()["candidates"] == []
            assert applied.json()["can_join"] is False

            duplicate_application = await guest_client.post(f"/api/v1/meals/{private_meal_id}/join")
            assert duplicate_application.status_code == 422

            host_private_view = await host_client.get(f"/api/v1/meals/{private_meal_id}")
            assert host_private_view.status_code == 200
            assert len(host_private_view.json()["candidates"]) == 1

            approved = await host_client.post(
                f"/api/v1/meals/{private_meal_id}/members/{guest_id}/approve"
            )
            assert approved.status_code == 200
            assert approved.json()["member_count"] == 2
            approved_member_view = await guest_client.get(f"/api/v1/meals/{private_meal_id}")
            assert approved_member_view.status_code == 200
            assert len(approved_member_view.json()["candidates"]) == 1

            cancellable = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "public",
                    "title": "可解除的約飯",
                    "description": None,
                    "scheduled_at": (now + timedelta(minutes=29)).isoformat(),
                    "join_deadline": (now + timedelta(minutes=14)).isoformat(),
                    "capacity": 2,
                    "restaurant_mode": "direct",
                    "restaurant_id": str(first_restaurant_id),
                },
            )
            assert cancellable.status_code == 201
            cancellable_id = cancellable.json()["id"]
            cancelled = await host_client.post(f"/api/v1/meals/{cancellable_id}/cancel")
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
            mine_after_cancel = await host_client.get("/api/v1/meals", params={"scope": "mine"})
            assert mine_after_cancel.status_code == 200
            assert all(item["id"] != cancellable_id for item in mine_after_cancel.json()["meals"])

            invalid_deadline = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "public",
                    "title": "截止時間不合法",
                    "description": None,
                    "scheduled_at": (now + timedelta(minutes=40)).isoformat(),
                    "join_deadline": (now + timedelta(minutes=2)).isoformat(),
                    "capacity": 4,
                    "restaurant_mode": "direct",
                    "restaurant_id": str(first_restaurant_id),
                },
            )
            assert invalid_deadline.status_code == 422

            awaiting = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "public",
                    "title": "截止後確認人數",
                    "description": None,
                    "scheduled_at": (now + timedelta(minutes=26)).isoformat(),
                    "join_deadline": (now + timedelta(minutes=11)).isoformat(),
                    "capacity": 4,
                    "restaurant_mode": "direct",
                    "restaurant_id": str(first_restaurant_id),
                },
            )
            assert awaiting.status_code == 201
            awaiting_id = awaiting.json()["id"]
            assert (await guest_client.post(f"/api/v1/meals/{awaiting_id}/join")).status_code == 200
            async with session_factory() as session:
                deadline_meal = await session.get(MealEvent, uuid.UUID(awaiting_id))
                assert deadline_meal is not None
                deadline_meal.join_deadline = now - timedelta(seconds=1)
                await session.commit()

            host_waiting = await host_client.get(f"/api/v1/meals/{awaiting_id}")
            assert host_waiting.status_code == 200
            assert host_waiting.json()["status"] == "awaiting_host_decision"
            assert (
                await guest_client.post(f"/api/v1/meals/{awaiting_id}/start-with-current-members")
            ).status_code == 403
            started = await host_client.post(
                f"/api/v1/meals/{awaiting_id}/start-with-current-members"
            )
            assert started.status_code == 200
            assert started.json()["status"] == "decided"

            underfilled = await host_client.post(
                "/api/v1/meals",
                json={
                    "visibility": "public",
                    "title": "一人截止自動解除",
                    "description": None,
                    "scheduled_at": (now + timedelta(minutes=27)).isoformat(),
                    "join_deadline": (now + timedelta(minutes=12)).isoformat(),
                    "capacity": 4,
                    "restaurant_mode": "direct",
                    "restaurant_id": str(first_restaurant_id),
                },
            )
            assert underfilled.status_code == 201
            underfilled_id = underfilled.json()["id"]
            async with session_factory() as session:
                deadline_meal = await session.get(MealEvent, uuid.UUID(underfilled_id))
                assert deadline_meal is not None
                deadline_meal.join_deadline = now - timedelta(seconds=1)
                await session.commit()
            mine_after_deadline = await host_client.get("/api/v1/meals", params={"scope": "mine"})
            assert mine_after_deadline.status_code == 200
            assert all(item["id"] != underfilled_id for item in mine_after_deadline.json()["meals"])
    finally:
        async with session_factory() as session:
            await session.execute(delete(MealEvent).where(MealEvent.host_user_id == host_id))
            await session.execute(
                delete(Restaurant).where(
                    Restaurant.id.in_([first_restaurant_id, second_restaurant_id])
                )
            )
            await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
            await session.execute(delete(User).where(User.id.in_([host_id, guest_id])))
            await session.commit()
