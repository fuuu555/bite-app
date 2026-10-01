"""Stage 6 review and favorite integration tests / Stage 6 留言與收藏整合測試。"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.database import session_factory
from api.core.security import create_user_session
from api.domain.models import Cuisine, Restaurant, User, UserProfile
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


@pytest.mark.asyncio
async def test_review_timeline_soft_delete_and_latest_stats() -> None:
    unique = uuid.uuid4().hex
    cuisine_id = uuid.uuid4()
    restaurant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    user_token: str | None = None
    other_token: str | None = None

    async with session_factory() as session:
        session.add(
            Cuisine(
                id=cuisine_id,
                slug=f"review-{unique}",
                display_name="留言測試料理",
                color="#F26B4F",
                icon_key="bowl",
                is_active=True,
            )
        )
        session.add(
            Restaurant(
                id=restaurant_id,
                name="Stage 6 留言測試店",
                address="桃園市中壢區測試路 6 號",
                primary_cuisine_id=cuisine_id,
                price_range="200_to_400",
                status="published",
                source_type="manual",
            )
        )
        user = User(
            id=user_id,
            email=f"review-{unique}@example.test",
            password_hash=None,
            role="user",
            is_active=True,
        )
        other_user = User(
            id=other_user_id,
            email=f"review-other-{unique}@example.test",
            password_hash=None,
            role="user",
            is_active=True,
        )
        session.add_all(
            [
                user,
                other_user,
                UserProfile(user_id=user_id, display_name="留言測試者"),
                UserProfile(user_id=other_user_id, display_name="另一位測試者"),
            ]
        )
        await session.flush()
        _, user_token = await create_user_session(session, user, "留言測試瀏覽器")
        _, other_token = await create_user_session(session, other_user, "另一個測試瀏覽器")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as user_client:
            user_client.cookies.set("bitemap_user_session", user_token)
            first = await user_client.post(
                f"/api/v1/explore/restaurants/{restaurant_id}/reviews",
                json={
                    "content": "第一次來覺得很舒服",
                    "revisit_status": "will_return",
                    "reason_ids": [],
                },
            )
            assert first.status_code == 201
            first_review_id = first.json()["id"]
            assert first.json()["is_edited"] is False
            assert first.json()["entry_number"] == 1
            assert first.json()["is_revisit"] is False

            second = await user_client.post(
                f"/api/v1/explore/restaurants/{restaurant_id}/reviews",
                json={
                    "content": "第二次來改成普通",
                    "revisit_status": "neutral",
                    "reason_ids": [],
                },
            )
            assert second.status_code == 201
            second_review_id = second.json()["id"]
            assert second.json()["thread_id"] == first.json()["thread_id"]
            assert second.json()["entry_number"] == 2
            assert second.json()["is_revisit"] is True

            current = await user_client.get(f"/api/v1/explore/restaurants/{restaurant_id}/reviews")
            assert current.status_code == 200
            assert current.json()["has_current_user_review"] is True
            assert len(current.json()["reviews"]) == 1
            assert current.json()["reviews"][0]["id"] == second_review_id
            assert current.json()["reviews"][0]["revisit_count"] == 2

            detail = await user_client.get(f"/api/v1/explore/restaurants/{restaurant_id}")
            assert detail.json()["app"]["rating_count"] == 1
            assert detail.json()["app"]["neutral_count"] == 1
            assert detail.json()["app"]["will_return_count"] == 0

            timeline = await user_client.get(
                f"/api/v1/explore/restaurants/{restaurant_id}/reviews/{second_review_id}/timeline"
            )
            assert timeline.status_code == 200
            assert [item["id"] for item in timeline.json()["reviews"]] == [
                first_review_id,
                second_review_id,
            ]

            edited = await user_client.patch(
                f"/api/v1/reviews/{second_review_id}",
                json={
                    "content": "第二次來補充服務很穩定",
                    "revisit_status": "neutral",
                    "reason_ids": [],
                },
            )
            assert edited.status_code == 200
            assert edited.json()["is_edited"] is True

            deleted = await user_client.delete(f"/api/v1/reviews/{second_review_id}")
            assert deleted.status_code == 204

            after_delete = await user_client.get(
                f"/api/v1/explore/restaurants/{restaurant_id}/reviews"
            )
            assert after_delete.status_code == 200
            assert after_delete.json()["reviews"][0]["id"] == first_review_id

            restored_stats = await user_client.get(f"/api/v1/explore/restaurants/{restaurant_id}")
            assert restored_stats.json()["app"]["will_return_count"] == 1
            assert restored_stats.json()["app"]["neutral_count"] == 0

            timeline_after_delete = await user_client.get(
                f"/api/v1/explore/restaurants/{restaurant_id}/reviews/{first_review_id}/timeline"
            )
            assert timeline_after_delete.status_code == 200
            assert [item["id"] for item in timeline_after_delete.json()["reviews"]] == [
                first_review_id,
                second_review_id,
            ]
            assert timeline_after_delete.json()["reviews"][1]["is_deleted"] is True

            liked = await user_client.post(f"/api/v1/reviews/{first_review_id}/like")
            assert liked.status_code == 200
            assert liked.json() == {"liked": True, "like_count": 1}
            repeated_like = await user_client.post(f"/api/v1/reviews/{first_review_id}/like")
            assert repeated_like.status_code == 200
            assert repeated_like.json()["like_count"] == 1

            favorite = await user_client.post(f"/api/v1/restaurants/{restaurant_id}/favorite")
            assert favorite.status_code == 204
            favorites = await user_client.get("/api/v1/me/favorites")
            assert favorites.status_code == 200
            assert [item["id"] for item in favorites.json()["restaurants"]] == [str(restaurant_id)]

            profile_reviews = await user_client.get("/api/v1/me/reviews")
            assert profile_reviews.status_code == 200
            assert profile_reviews.json()["total"] == 1
            assert profile_reviews.json()["reviews"][0]["restaurant_id"] == str(restaurant_id)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as other_client:
            other_client.cookies.set("bitemap_user_session", other_token)
            forbidden = await other_client.patch(
                f"/api/v1/reviews/{first_review_id}",
                json={"content": "不能修改別人的留言"},
            )
            assert forbidden.status_code == 403
    finally:
        async with session_factory() as session:
            await session.execute(delete(Restaurant).where(Restaurant.id == restaurant_id))
            await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
            await session.execute(delete(User).where(User.id.in_([user_id, other_user_id])))
            await session.commit()
