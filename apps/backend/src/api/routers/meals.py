"""Meal creation, membership, and public voting endpoints / 約飯建立、成員與公開投票端點。"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import UserSessionContext, require_user
from api.domain.models import MealEvent, MealMembership
from api.domain.schemas import (
    MealCandidateCreateRequest,
    MealCreateRequest,
    MealListResponse,
    MealResponse,
    MealVoteRequest,
)
from api.services.meals import (
    LIVE_MEAL_STATUSES,
    add_candidate,
    cancel_meal,
    cast_vote,
    create_meal,
    finalize_vote,
    get_meal,
    join_meal,
    leave_meal,
    meal_response,
    refresh_public_meal_state,
    remove_candidate,
    remove_member,
    review_member,
    start_voting,
    start_with_current_members,
)

router = APIRouter(prefix="/api/v1", tags=["meals"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UserSessionContext, Depends(require_user)]


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


async def _meal_or_404(session: AsyncSession, meal_id: uuid.UUID) -> MealEvent:
    meal = await get_meal(session, meal_id)
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meal not found")
    return meal


@router.get("/meals", response_model=MealListResponse)
async def read_meals(
    session: SessionDep,
    current: UserDep,
    scope: Annotated[Literal["public", "mine"], Query()] = "public",
) -> MealListResponse:
    """List discoverable meals or a user's active involvement.

    列出可探索或使用者自己的有效約飯。
    """
    statement = select(MealEvent.id).where(MealEvent.status.in_(LIVE_MEAL_STATUSES))
    if scope == "mine":
        statement = statement.join(MealMembership).where(
            MealMembership.user_id == current.user.id,
            MealMembership.membership_status.in_(("host", "member", "pending")),
        )
    else:
        # Private means approval-based, not hidden: people can discover and apply.
        # 私人指需審核而非完全隱藏，使用者仍可看見並申請。
        statement = statement.where(MealEvent.status.in_(LIVE_MEAL_STATUSES))
    meal_ids = (await session.scalars(statement.order_by(MealEvent.scheduled_at.asc()))).all()
    meals: list[MealResponse] = []
    for meal_id in meal_ids:
        meal = await _meal_or_404(session, meal_id)
        if await refresh_public_meal_state(session, meal):
            meal = await _meal_or_404(session, meal_id)
        if meal.status not in LIVE_MEAL_STATUSES:
            continue
        meals.append(await meal_response(session, meal, current.user.id))
    return MealListResponse(meals=meals)


@router.post("/meals", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
async def write_meal(
    payload: MealCreateRequest,
    session: SessionDep,
    current: UserDep,
) -> MealResponse:
    try:
        meal = await create_meal(session, current.user, payload)
    except ValueError as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.get("/meals/{meal_id}", response_model=MealResponse)
async def read_meal(meal_id: uuid.UUID, session: SessionDep, current: UserDep) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    if meal.status == "cancelled":
        # A known cancelled meal is different from an unknown identifier.
        # 已解除飯局需讓前端能顯示明確通知，不與不存在的 ID 混為一談。
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="meal cancelled")
    if meal.status not in LIVE_MEAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meal not found")
    if await refresh_public_meal_state(session, meal):
        meal = await _meal_or_404(session, meal_id)
    if meal.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="meal cancelled")
    if meal.status not in LIVE_MEAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meal not found")
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/join", response_model=MealResponse)
async def join_existing_meal(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await join_meal(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/leave", response_model=MealResponse)
async def leave_existing_meal(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await leave_meal(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/cancel", response_model=MealResponse)
async def cancel_existing_meal(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    """Allow only the host to soft-cancel an active meal / 僅允許發起人軟解除有效約飯。"""
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await cancel_meal(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/members/{user_id}/approve", response_model=MealResponse)
async def approve_private_member(
    meal_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await review_member(session, meal, current.user.id, user_id, approved=True)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/members/{user_id}/reject", response_model=MealResponse)
async def reject_private_member(
    meal_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await review_member(session, meal, current.user.id, user_id, approved=False)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/members/{user_id}/remove", response_model=MealResponse)
async def remove_existing_member(
    meal_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await remove_member(session, meal, current.user.id, user_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/candidates", response_model=MealResponse)
async def add_meal_candidate(
    meal_id: uuid.UUID,
    payload: MealCandidateCreateRequest,
    session: SessionDep,
    current: UserDep,
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await add_candidate(session, meal, current.user.id, payload.restaurant_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.delete("/meals/{meal_id}/candidates/{candidate_id}", response_model=MealResponse)
async def delete_meal_candidate(
    meal_id: uuid.UUID, candidate_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await remove_candidate(session, meal, current.user.id, candidate_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/start-voting", response_model=MealResponse)
async def start_meal_voting(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await start_voting(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/start-with-current-members", response_model=MealResponse)
async def start_with_available_members(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    """Confirm a viable room after joining closes / 確認截止後以現有人數成團。"""
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await start_with_current_members(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/votes", response_model=MealResponse)
async def write_meal_vote(
    meal_id: uuid.UUID, payload: MealVoteRequest, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await cast_vote(session, meal, current.user.id, payload.candidate_id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)


@router.post("/meals/{meal_id}/finalize-vote", response_model=MealResponse)
async def finalize_meal_vote(
    meal_id: uuid.UUID, session: SessionDep, current: UserDep
) -> MealResponse:
    meal = await _meal_or_404(session, meal_id)
    try:
        meal = await finalize_vote(session, meal, current.user.id)
    except (ValueError, PermissionError, LookupError) as error:
        raise _http_error(error) from error
    return await meal_response(session, meal, current.user.id)
