"""Review, revisit, like, and favorite services / 留言、再訪、按讚與收藏服務。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Select, case, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import (
    Restaurant,
    RestaurantFavorite,
    RestaurantReview,
    RestaurantReviewThread,
    ReviewLike,
    ReviewReason,
    User,
    UserProfile,
)
from api.domain.schemas import (
    ExploreAppSignalsResponse,
    FavoriteRestaurantResponse,
    MapCuisineResponse,
    ProfileReviewResponse,
    ReviewCreateRequest,
    ReviewLikeResponse,
    ReviewReasonResponse,
    ReviewResponse,
    ReviewSort,
    ReviewStatusFilter,
    ReviewUpdateRequest,
)
from api.services.profile import avatar_url_for_profile


async def get_restaurant_app_stats(
    session: AsyncSession,
    restaurant_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ExploreAppSignalsResponse]:
    """Aggregate the latest effective event per user / 聚合每位使用者最新有效事件。"""
    if not restaurant_ids:
        return {}

    latest = _latest_effective_reviews(restaurant_ids).subquery()
    statement = (
        select(
            latest.c.restaurant_id,
            func.count(latest.c.review_id).label("rating_count"),
            func.sum(case((latest.c.revisit_status == "will_return", 1), else_=0)).label(
                "will_return_count"
            ),
            func.sum(case((latest.c.revisit_status == "neutral", 1), else_=0)).label(
                "neutral_count"
            ),
            func.sum(case((latest.c.revisit_status == "will_not_return", 1), else_=0)).label(
                "will_not_return_count"
            ),
        )
        .where(latest.c.row_number == 1)
        .group_by(latest.c.restaurant_id)
    )
    stats: dict[uuid.UUID, ExploreAppSignalsResponse] = {}
    for row in (await session.execute(statement)).all():
        count = int(row.rating_count)
        will_return_count = int(row.will_return_count or 0)
        stats[row.restaurant_id] = ExploreAppSignalsResponse(
            revisit_rate=(round(will_return_count / count * 100, 1) if count else None),
            rating_count=count,
            will_return_count=will_return_count,
            neutral_count=int(row.neutral_count or 0),
            will_not_return_count=int(row.will_not_return_count or 0),
        )
    return stats


def _latest_effective_reviews(restaurant_ids: list[uuid.UUID]) -> Select[Any]:
    return select(
        RestaurantReview.id.label("review_id"),
        RestaurantReview.thread_id,
        RestaurantReview.restaurant_id,
        RestaurantReview.user_id,
        RestaurantReview.revisit_status,
        func.row_number()
        .over(
            partition_by=RestaurantReview.thread_id,
            order_by=(RestaurantReview.created_at.desc(), RestaurantReview.id.desc()),
        )
        .label("row_number"),
    ).where(
        RestaurantReview.restaurant_id.in_(restaurant_ids),
        RestaurantReview.deleted_at.is_(None),
    )


async def list_review_reasons(session: AsyncSession) -> list[ReviewReason]:
    result = await session.execute(
        select(ReviewReason)
        .where(ReviewReason.is_active.is_(True))
        .order_by(ReviewReason.polarity, ReviewReason.display_name)
    )
    return list(result.scalars())


async def get_review_reasons_by_ids(
    session: AsyncSession,
    reason_ids: list[uuid.UUID],
) -> list[ReviewReason]:
    if not reason_ids:
        return []
    result = await session.execute(
        select(ReviewReason)
        .where(ReviewReason.id.in_(reason_ids), ReviewReason.is_active.is_(True))
        .order_by(ReviewReason.polarity, ReviewReason.display_name)
    )
    reasons = list(result.scalars())
    if len(reasons) != len(set(reason_ids)):
        raise ValueError("one or more review reasons are unavailable")
    return reasons


async def get_published_restaurant(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
) -> Restaurant | None:
    return await session.scalar(
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine), selectinload(Restaurant.photos))
        .where(Restaurant.id == restaurant_id, Restaurant.status == "published")
    )


async def create_review(
    session: AsyncSession,
    restaurant: Restaurant,
    user: User,
    payload: ReviewCreateRequest,
) -> RestaurantReview:
    # Lock the single thread before assigning its next entry number so every
    # Keep revisits ordered under the original review thread.
    # 鎖定留言串後再編號，確保再訪紀錄掛在原留言底下。
    await session.execute(
        pg_insert(cast(Any, RestaurantReviewThread.__table__))
        .values(
            id=uuid.uuid4(),
            restaurant_id=restaurant.id,
            user_id=user.id,
        )
        .on_conflict_do_nothing(
            index_elements=[
                RestaurantReviewThread.restaurant_id,
                RestaurantReviewThread.user_id,
            ]
        )
    )
    thread = await session.scalar(
        select(RestaurantReviewThread)
        .where(
            RestaurantReviewThread.restaurant_id == restaurant.id,
            RestaurantReviewThread.user_id == user.id,
        )
        .with_for_update()
    )
    if thread is None:
        raise ValueError("review thread could not be created")
    last_entry_number = await session.scalar(
        select(func.max(RestaurantReview.entry_number)).where(
            RestaurantReview.thread_id == thread.id
        )
    )
    reasons = await get_review_reasons_by_ids(session, payload.reason_ids)
    review = RestaurantReview(
        thread_id=thread.id,
        entry_number=int(last_entry_number or 0) + 1,
        restaurant_id=restaurant.id,
        user_id=user.id,
        content=payload.content,
        revisit_status=payload.revisit_status,
        reasons=reasons,
    )
    session.add(review)
    await session.commit()
    return await get_review_for_response(session, review.id)


async def get_review_for_response(
    session: AsyncSession,
    review_id: uuid.UUID,
) -> RestaurantReview:
    review = await session.scalar(
        select(RestaurantReview)
        .options(
            selectinload(RestaurantReview.user)
            .selectinload(User.profile)
            .options(selectinload(UserProfile.avatar_asset)),
            selectinload(RestaurantReview.reasons),
        )
        .where(RestaurantReview.id == review_id)
    )
    if review is None:
        raise ValueError("review not found")
    return review


async def list_reviews(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    *,
    sort: ReviewSort,
    status_filter: ReviewStatusFilter,
    current_user_id: uuid.UUID | None,
) -> tuple[list[RestaurantReview], int, dict[uuid.UUID, int], set[uuid.UUID]]:
    """List one current entry per thread / 每條留言串只列最新有效紀錄。"""
    latest = _latest_effective_reviews([restaurant_id]).subquery()
    statement = (
        select(RestaurantReview)
        .join(latest, latest.c.review_id == RestaurantReview.id)
        .options(
            selectinload(RestaurantReview.user)
            .selectinload(User.profile)
            .options(selectinload(UserProfile.avatar_asset)),
            selectinload(RestaurantReview.reasons),
        )
        .where(latest.c.row_number == 1)
    )
    if status_filter != "all":
        statement = statement.where(RestaurantReview.revisit_status == status_filter)
    reviews = list((await session.execute(statement)).scalars())
    if not reviews:
        return [], 0, {}, set()

    review_ids = [review.id for review in reviews]
    like_rows = await session.execute(
        select(ReviewLike.review_id, func.count(ReviewLike.user_id))
        .where(ReviewLike.review_id.in_(review_ids))
        .group_by(ReviewLike.review_id)
    )
    like_counts = {review_id: int(count) for review_id, count in like_rows.all()}
    liked_by_me: set[uuid.UUID] = set()
    if current_user_id is not None:
        liked_by_me = set(
            await session.scalars(
                select(ReviewLike.review_id).where(
                    ReviewLike.review_id.in_(review_ids),
                    ReviewLike.user_id == current_user_id,
                )
            )
        )

    if sort == "latest":
        reviews.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    elif sort == "popular":
        reviews.sort(key=lambda item: (like_counts.get(item.id, 0), item.created_at), reverse=True)
    else:
        # A bounded, explainable MVP score: likes dominate, then recency.
        # MVP 使用可解釋的有限排序：按讚優先，再以時間新舊排序。
        reviews.sort(
            key=lambda item: (
                like_counts.get(item.id, 0),
                item.created_at,
            ),
            reverse=True,
        )
    return reviews, len(reviews), like_counts, liked_by_me


async def has_review_history(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> bool:
    """Check whether the current user has any entry, including soft-deleted history."""
    if user_id is None:
        return False
    return bool(
        await session.scalar(
            select(
                exists().where(
                    RestaurantReview.restaurant_id == restaurant_id,
                    RestaurantReview.user_id == user_id,
                )
            )
        )
    )


async def list_profile_reviews(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ProfileReviewResponse], int]:
    """List the current user's visible review entries / 列出使用者可見留言紀錄。"""
    statement = (
        select(RestaurantReview)
        .join(Restaurant, Restaurant.id == RestaurantReview.restaurant_id)
        .options(
            selectinload(RestaurantReview.reasons),
            selectinload(RestaurantReview.restaurant).selectinload(Restaurant.primary_cuisine),
            selectinload(RestaurantReview.restaurant).selectinload(Restaurant.photos),
        )
        .where(
            RestaurantReview.user_id == user_id,
            RestaurantReview.deleted_at.is_(None),
            Restaurant.status == "published",
        )
        .order_by(RestaurantReview.updated_at.desc(), RestaurantReview.id.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = list((await session.execute(statement)).scalars())
    total = await session.scalar(
        select(func.count(RestaurantReview.id))
        .join(Restaurant, Restaurant.id == RestaurantReview.restaurant_id)
        .where(
            RestaurantReview.user_id == user_id,
            RestaurantReview.deleted_at.is_(None),
            Restaurant.status == "published",
        )
    )
    thread_ids = [entry.thread_id for entry in entries]
    revisit_counts: dict[uuid.UUID, int] = {}
    if thread_ids:
        rows = await session.execute(
            select(RestaurantReview.thread_id, func.count(RestaurantReview.id))
            .where(
                RestaurantReview.thread_id.in_(thread_ids),
                RestaurantReview.deleted_at.is_(None),
            )
            .group_by(RestaurantReview.thread_id)
        )
        revisit_counts = {thread_id: int(count) for thread_id, count in rows.all()}

    responses = [
        ProfileReviewResponse(
            id=entry.id,
            restaurant_id=entry.restaurant_id,
            restaurant_name=entry.restaurant.name,
            restaurant_photo_url=entry.restaurant.photos[0].url
            if entry.restaurant.photos
            else None,
            entry_number=entry.entry_number,
            is_revisit=entry.entry_number > 1,
            content=entry.content,
            revisit_status=entry.revisit_status,  # type: ignore[arg-type]
            reasons=[reason_response(reason) for reason in entry.reasons],
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            is_edited=entry.updated_at > entry.created_at,
            revisit_count=revisit_counts.get(entry.thread_id, 1),
        )
        for entry in entries
    ]
    return responses, int(total or 0)


async def count_revisits(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    thread_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not thread_ids:
        return {}
    rows = await session.execute(
        select(RestaurantReview.thread_id, func.count(RestaurantReview.id))
        .where(
            RestaurantReview.restaurant_id == restaurant_id,
            RestaurantReview.thread_id.in_(thread_ids),
        )
        .group_by(RestaurantReview.thread_id)
    )
    return {thread_id: int(count) for thread_id, count in rows.all()}


async def get_timeline(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    review_id: uuid.UUID,
) -> list[RestaurantReview]:
    source = await session.scalar(
        select(RestaurantReview).where(
            RestaurantReview.id == review_id,
            RestaurantReview.restaurant_id == restaurant_id,
        )
    )
    if source is None:
        raise ValueError("review not found")
    result = await session.execute(
        select(RestaurantReview)
        .options(
            selectinload(RestaurantReview.user)
            .selectinload(User.profile)
            .options(selectinload(UserProfile.avatar_asset)),
            selectinload(RestaurantReview.reasons),
        )
        .where(
            RestaurantReview.thread_id == source.thread_id,
        )
        .order_by(RestaurantReview.entry_number.asc())
    )
    return list(result.scalars())


async def review_like_response(
    session: AsyncSession,
    review_id: uuid.UUID,
    user_id: uuid.UUID,
    liked: bool,
) -> ReviewLikeResponse:
    existing = await session.scalar(
        select(ReviewLike).where(ReviewLike.review_id == review_id, ReviewLike.user_id == user_id)
    )
    if liked and existing is None:
        session.add(ReviewLike(review_id=review_id, user_id=user_id))
    elif not liked and existing is not None:
        await session.delete(existing)
    await session.commit()
    count = await session.scalar(
        select(func.count(ReviewLike.user_id)).where(ReviewLike.review_id == review_id)
    )
    return ReviewLikeResponse(liked=liked, like_count=int(count or 0))


def reason_response(reason: ReviewReason) -> ReviewReasonResponse:
    return ReviewReasonResponse(
        id=reason.id,
        slug=reason.slug,
        display_name=reason.display_name,
        polarity=reason.polarity,  # type: ignore[arg-type]
    )


async def review_response(
    session: AsyncSession,
    review: RestaurantReview,
    *,
    current_user_id: uuid.UUID | None,
    like_counts: dict[uuid.UUID, int] | None = None,
    liked_by_me: set[uuid.UUID] | None = None,
    revisit_counts: dict[uuid.UUID, int] | None = None,
) -> ReviewResponse:
    if like_counts is None:
        count = await session.scalar(
            select(func.count(ReviewLike.user_id)).where(ReviewLike.review_id == review.id)
        )
        like_count = int(count or 0)
    else:
        like_count = like_counts.get(review.id, 0)
    if liked_by_me is None:
        liked = (
            current_user_id is not None
            and await session.scalar(
                select(ReviewLike.review_id).where(
                    ReviewLike.review_id == review.id,
                    ReviewLike.user_id == current_user_id,
                )
            )
            is not None
        )
    else:
        liked = review.id in liked_by_me
    if revisit_counts is None:
        count = await session.scalar(
            select(func.count(RestaurantReview.id)).where(
                RestaurantReview.thread_id == review.thread_id,
            )
        )
        revisit_count = int(count or 0)
    else:
        revisit_count = revisit_counts.get(review.thread_id, 0)
    profile = review.user.profile
    return ReviewResponse(
        id=review.id,
        thread_id=review.thread_id,
        entry_number=review.entry_number,
        is_revisit=review.entry_number > 1,
        author_id=review.user_id,
        author_display_name=profile.display_name if profile else "BiteMap 使用者",
        author_avatar_url=avatar_url_for_profile(profile) if profile else None,
        content=review.content,
        revisit_status=review.revisit_status,  # type: ignore[arg-type]
        reasons=[reason_response(reason) for reason in review.reasons],
        created_at=review.created_at,
        updated_at=review.updated_at,
        is_edited=review.updated_at > review.created_at,
        is_deleted=review.deleted_at is not None,
        revisit_count=revisit_count,
        like_count=like_count,
        liked_by_me=liked,
        is_owner=current_user_id == review.user_id,
    )


async def update_review(
    session: AsyncSession,
    review: RestaurantReview,
    payload: ReviewUpdateRequest,
) -> RestaurantReview:
    if payload.content is not None:
        review.content = payload.content
    if payload.revisit_status is not None:
        review.revisit_status = payload.revisit_status
    if payload.reason_ids is not None:
        review.reasons = await get_review_reasons_by_ids(session, payload.reason_ids)
    review.updated_at = datetime.now(UTC)
    await session.commit()
    return await get_review_for_response(session, review.id)


async def soft_delete_review(session: AsyncSession, review: RestaurantReview) -> None:
    review.deleted_at = datetime.now(UTC)
    await session.commit()


async def favorite_card(
    restaurant: Restaurant,
    created_at: datetime,
) -> FavoriteRestaurantResponse:
    cuisine = restaurant.primary_cuisine
    if cuisine is None or restaurant.price_range is None:
        raise ValueError("restaurant is missing exploration fields")
    return FavoriteRestaurantResponse(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        primary_cuisine=MapCuisineResponse(
            id=cuisine.id,
            display_name=cuisine.display_name,
            color=cuisine.color,
            icon_key=cuisine.icon_key,
        ),
        price_range=restaurant.price_range,  # type: ignore[arg-type]
        menu_url=restaurant.menu_url,
        photo_url=restaurant.photos[0].url if restaurant.photos else None,
        created_at=created_at,
    )


async def is_favorited(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    return (
        await session.scalar(
            select(RestaurantFavorite.restaurant_id).where(
                RestaurantFavorite.restaurant_id == restaurant_id,
                RestaurantFavorite.user_id == user_id,
            )
        )
        is not None
    )
