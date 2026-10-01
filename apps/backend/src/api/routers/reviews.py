"""Restaurant review and favorite endpoints / 餐廳留言與收藏端點。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.database import get_session
from api.core.security import UserSessionContext, hash_session_token, require_user
from api.domain.models import (
    Restaurant,
    RestaurantFavorite,
    RestaurantReview,
    User,
    UserProfile,
    UserSession,
)
from api.domain.schemas import (
    FavoriteListResponse,
    FavoriteStateResponse,
    ProfileReviewListResponse,
    ReviewCreateRequest,
    ReviewLikeResponse,
    ReviewListResponse,
    ReviewResponse,
    ReviewSort,
    ReviewStatusFilter,
    ReviewTimelineResponse,
    ReviewUpdateRequest,
)
from api.services.reviews import (
    count_revisits,
    create_review,
    favorite_card,
    get_published_restaurant,
    get_timeline,
    has_review_history,
    is_favorited,
    list_profile_reviews,
    list_review_reasons,
    list_reviews,
    reason_response,
    review_like_response,
    review_response,
    soft_delete_review,
    update_review,
)

router = APIRouter(prefix="/api/v1", tags=["reviews"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UserSessionContext, Depends(require_user)]


async def optional_user(
    session: SessionDep,
    session_token: Annotated[str | None, Cookie(alias="bitemap_user_session")] = None,
) -> UserSessionContext | None:
    """Read an optional user session / 讀取可選的一般使用者 Session。"""
    if not session_token:
        return None
    result = await session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == hash_session_token(session_token),
            UserSession.expires_at > datetime.now(UTC),
            User.is_active.is_(True),
            User.role == "user",
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    return UserSessionContext(user=row[1], session=row[0])


async def _require_review_owner(
    session: AsyncSession,
    review_id: uuid.UUID,
    user_id: uuid.UUID,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    if review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="review owner required")
    if review.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return review


@router.get(
    "/explore/restaurants/{restaurant_id}/reviews",
    response_model=ReviewListResponse,
)
async def read_restaurant_reviews(
    restaurant_id: uuid.UUID,
    session: SessionDep,
    current: Annotated[UserSessionContext | None, Depends(optional_user)],
    sort: Annotated[ReviewSort, Query()] = "featured",
    status_filter: Annotated[ReviewStatusFilter, Query(alias="status")] = "all",
) -> ReviewListResponse:
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    reviews, total, like_counts, liked_by_me = await list_reviews(
        session,
        restaurant_id,
        sort=sort,
        status_filter=status_filter,
        current_user_id=current.user.id if current else None,
    )
    revisit_counts = await count_revisits(
        session,
        restaurant_id,
        [review.thread_id for review in reviews],
    )
    responses = [
        await review_response(
            session,
            review,
            current_user_id=current.user.id if current else None,
            like_counts=like_counts,
            liked_by_me=liked_by_me,
            revisit_counts=revisit_counts,
        )
        for review in reviews
    ]
    return ReviewListResponse(
        reviews=responses,
        total=total,
        sort=sort,
        status=status_filter,
        available_reasons=[
            reason_response(reason) for reason in await list_review_reasons(session)
        ],
        has_current_user_review=await has_review_history(
            session,
            restaurant_id,
            current.user.id if current else None,
        ),
    )


@router.post(
    "/explore/restaurants/{restaurant_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def write_restaurant_review(
    restaurant_id: uuid.UUID,
    payload: ReviewCreateRequest,
    session: SessionDep,
    current: UserDep,
) -> ReviewResponse:
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    try:
        review = await create_review(session, restaurant, current.user, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return await review_response(session, review, current_user_id=current.user.id)


@router.get(
    "/explore/restaurants/{restaurant_id}/reviews/{review_id}/timeline",
    response_model=ReviewTimelineResponse,
)
async def read_review_timeline(
    restaurant_id: uuid.UUID,
    review_id: uuid.UUID,
    session: SessionDep,
    current: Annotated[UserSessionContext | None, Depends(optional_user)],
) -> ReviewTimelineResponse:
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    try:
        reviews = await get_timeline(session, restaurant_id, review_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    revisit_counts = {reviews[0].thread_id: len(reviews)} if reviews else {}
    responses = [
        await review_response(
            session,
            review,
            current_user_id=current.user.id if current else None,
            revisit_counts=revisit_counts,
        )
        for review in reviews
    ]
    return ReviewTimelineResponse(reviews=responses)


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def edit_review(
    review_id: uuid.UUID,
    payload: ReviewUpdateRequest,
    session: SessionDep,
    current: UserDep,
) -> ReviewResponse:
    review = await _require_review_owner(session, review_id, current.user.id)
    try:
        updated = await update_review(session, review, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return await review_response(session, updated, current_user_id=current.user.id)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> Response:
    review = await _require_review_owner(session, review_id, current.user.id)
    await soft_delete_review(session, review)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reviews/{review_id}/like", response_model=ReviewLikeResponse)
async def like_review(
    review_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> ReviewLikeResponse:
    review = await session.scalar(
        select(RestaurantReview).where(
            RestaurantReview.id == review_id,
            RestaurantReview.deleted_at.is_(None),
        )
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    try:
        return await review_like_response(session, review_id, current.user.id, True)
    except IntegrityError:
        await session.rollback()
        return await review_like_response(session, review_id, current.user.id, True)


@router.delete("/reviews/{review_id}/like", response_model=ReviewLikeResponse)
async def unlike_review(
    review_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> ReviewLikeResponse:
    review = await session.scalar(
        select(RestaurantReview).where(
            RestaurantReview.id == review_id,
            RestaurantReview.deleted_at.is_(None),
        )
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return await review_like_response(session, review_id, current.user.id, False)


@router.get("/me/favorites", response_model=FavoriteListResponse)
async def read_my_favorites(
    session: SessionDep,
    current: UserDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FavoriteListResponse:
    statement = (
        select(RestaurantFavorite, Restaurant)
        .join(Restaurant, Restaurant.id == RestaurantFavorite.restaurant_id)
        .options(selectinload(Restaurant.primary_cuisine), selectinload(Restaurant.photos))
        .where(
            RestaurantFavorite.user_id == current.user.id,
            Restaurant.status == "published",
        )
        .order_by(RestaurantFavorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(statement)).all()
    total = await session.scalar(
        select(func.count())
        .select_from(RestaurantFavorite)
        .join(Restaurant, Restaurant.id == RestaurantFavorite.restaurant_id)
        .where(
            RestaurantFavorite.user_id == current.user.id,
            Restaurant.status == "published",
        )
    )
    return FavoriteListResponse(
        restaurants=[
            await favorite_card(restaurant, favorite.created_at) for favorite, restaurant in rows
        ],
        total=int(total or 0),
    )


@router.get("/me/reviews", response_model=ProfileReviewListResponse)
async def read_my_reviews(
    session: SessionDep,
    current: UserDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProfileReviewListResponse:
    reviews, total = await list_profile_reviews(session, current.user.id, limit, offset)
    return ProfileReviewListResponse(reviews=reviews, total=total)


@router.post("/restaurants/{restaurant_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    restaurant_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> Response:
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    if not await is_favorited(session, restaurant_id, current.user.id):
        session.add(RestaurantFavorite(restaurant_id=restaurant_id, user_id=current.user.id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/restaurants/{restaurant_id}/favorite", response_model=FavoriteStateResponse)
async def read_favorite_state(
    restaurant_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> FavoriteStateResponse:
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    return FavoriteStateResponse(
        favorited=await is_favorited(session, restaurant_id, current.user.id),
    )


@router.delete("/restaurants/{restaurant_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    restaurant_id: uuid.UUID,
    session: SessionDep,
    current: UserDep,
) -> Response:
    await session.execute(
        delete(RestaurantFavorite).where(
            RestaurantFavorite.restaurant_id == restaurant_id,
            RestaurantFavorite.user_id == current.user.id,
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
