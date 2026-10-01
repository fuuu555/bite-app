"""Meal workflow rules / 約飯流程規則。"""

from __future__ import annotations

import random
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import (
    MealCandidate,
    MealEvent,
    MealMembership,
    MealVote,
    Restaurant,
    User,
    UserProfile,
)
from api.domain.schemas import (
    MealCandidateResponse,
    MealCreateRequest,
    MealMemberResponse,
    MealMembershipStatus,
    MealResponse,
    MealRestaurantResponse,
    MealStatus,
    MealVisibility,
)
from api.services.profile import avatar_url_for_profile

FORMAL_MEMBERSHIP_STATUSES = ("host", "member")
LIVE_MEAL_STATUSES = ("open", "awaiting_host_decision", "voting", "decided")


def _meal_options():
    """Load every relationship needed to build a meal response / 載入約飯回應需要的關聯。"""
    return (
        selectinload(MealEvent.host)
        .selectinload(User.profile)
        .options(selectinload(UserProfile.tags), selectinload(UserProfile.avatar_asset)),
        selectinload(MealEvent.memberships)
        .selectinload(MealMembership.user)
        .selectinload(User.profile)
        .options(selectinload(UserProfile.tags), selectinload(UserProfile.avatar_asset)),
        selectinload(MealEvent.candidates)
        .selectinload(MealCandidate.restaurant)
        .selectinload(Restaurant.primary_cuisine),
        selectinload(MealEvent.candidates)
        .selectinload(MealCandidate.restaurant)
        .selectinload(Restaurant.photos),
        selectinload(MealEvent.decided_restaurant).selectinload(Restaurant.primary_cuisine),
        selectinload(MealEvent.decided_restaurant).selectinload(Restaurant.photos),
    )


async def get_meal(session: AsyncSession, meal_id: uuid.UUID) -> MealEvent | None:
    """Fetch a meal with response relationships / 取得可直接回應的約飯。"""
    return await session.scalar(
        select(MealEvent)
        .options(*_meal_options())
        .execution_options(populate_existing=True)
        .where(MealEvent.id == meal_id)
    )


async def get_published_restaurant(
    session: AsyncSession, restaurant_id: uuid.UUID
) -> Restaurant | None:
    """Only published restaurants can become meal candidates / 只有已發布店家可作為約飯候選。"""
    return await session.scalar(
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine), selectinload(Restaurant.photos))
        .where(Restaurant.id == restaurant_id, Restaurant.status == "published")
    )


def formal_members(meal: MealEvent) -> list[MealMembership]:
    return [
        member
        for member in meal.memberships
        if member.membership_status in FORMAL_MEMBERSHIP_STATUSES
    ]


def membership_for(meal: MealEvent, user_id: uuid.UUID) -> MealMembership | None:
    return next((member for member in meal.memberships if member.user_id == user_id), None)


async def refresh_public_meal_state(session: AsyncSession, meal: MealEvent) -> bool:
    """Resolve public capacity and deadline state / 收斂公開約飯的額滿與截止狀態。"""
    if meal.visibility != "public" or meal.status != "open":
        return False

    now = datetime.now(UTC)
    member_count = len(formal_members(meal))
    deadline_reached = meal.join_deadline is not None and meal.join_deadline <= now
    if member_count < meal.capacity and not deadline_reached:
        return False

    # Full rooms continue immediately; a direct meal is already decided, while a ballot opens.
    # 額滿可直接繼續：已選店的飯局成團，投票飯局開始投票。
    if member_count >= meal.capacity:
        if meal.decided_restaurant_id is not None:
            meal.status = "decided"
        elif meal.candidates:
            meal.status = "voting"
        else:
            meal.status = "awaiting_host_decision"
    elif member_count < 2:
        # A one-person room cannot become a meal after its join window has closed.
        # 截止時未滿兩人，沒有成團意義，改為軟取消。
        meal.status = "cancelled"
    else:
        # Keep the host in control when a viable but not-full room reaches its deadline.
        # 截止後已有兩人但未額滿，由發起人決定以目前人數開始或解除。
        meal.status = "awaiting_host_decision"
    await session.commit()
    return True


async def create_meal(
    session: AsyncSession,
    host: User,
    payload: MealCreateRequest,
) -> MealEvent:
    """Persist a meal and its host membership / 建立約飯與發起人的正式成員資格。"""
    if payload.scheduled_at <= datetime.now(UTC):
        raise ValueError("scheduled time must be in the future")
    if payload.join_deadline is not None and payload.join_deadline >= payload.scheduled_at:
        raise ValueError("join deadline must be before the meal time")
    if payload.visibility == "private" and payload.restaurant_mode == "vote":
        # Private voting is intentionally left TBD in the product requirements.
        # 私人約飯的投票規則尚未定案，因此此階段不擅自啟用。
        raise ValueError("private meal voting is not available yet")
    if payload.visibility == "public":
        if payload.join_deadline is None:
            raise ValueError("public meals need a join deadline")
        minutes_before = (payload.scheduled_at - payload.join_deadline).total_seconds() / 60
        if not 5 <= minutes_before <= 30:
            raise ValueError("join deadline must be 5 to 30 minutes before the meal")
        if payload.join_deadline <= datetime.now(UTC):
            raise ValueError("join deadline must be in the future")
    elif payload.join_deadline is not None:
        raise ValueError("private meals do not use a join deadline")

    restaurant = None
    if payload.restaurant_id is not None:
        restaurant = await get_published_restaurant(session, payload.restaurant_id)
        if restaurant is None:
            raise ValueError("restaurant must be published")

    meal = MealEvent(
        host_user_id=host.id,
        visibility=payload.visibility,
        title=payload.title,
        description=payload.description,
        scheduled_at=payload.scheduled_at,
        join_deadline=payload.join_deadline,
        capacity=payload.capacity,
        decided_restaurant_id=restaurant.id
        if payload.restaurant_mode == "direct" and restaurant
        else None,
    )
    session.add(meal)
    await session.flush()
    session.add(MealMembership(meal_event_id=meal.id, user_id=host.id, membership_status="host"))
    if payload.restaurant_mode == "vote" and restaurant is not None:
        session.add(MealCandidate(meal_event_id=meal.id, restaurant_id=restaurant.id, position=1))
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def add_candidate(
    session: AsyncSession, meal: MealEvent, actor_id: uuid.UUID, restaurant_id: uuid.UUID
) -> MealEvent:
    """Add one of at most three public ballot choices.

    新增最多三家中的一個公開投票候選。
    """
    if meal.host_user_id != actor_id:
        raise PermissionError("meal host required")
    if (
        meal.visibility != "public"
        or meal.status not in ("open", "awaiting_host_decision")
        or meal.decided_restaurant_id is not None
    ):
        raise ValueError("candidates can only be edited before public voting starts")
    if len(meal.candidates) >= 3:
        raise ValueError("a meal can have at most three candidates")
    if any(candidate.restaurant_id == restaurant_id for candidate in meal.candidates):
        raise ValueError("restaurant is already a candidate")
    restaurant = await get_published_restaurant(session, restaurant_id)
    if restaurant is None:
        raise ValueError("restaurant must be published")
    session.add(
        MealCandidate(
            meal_event_id=meal.id,
            restaurant_id=restaurant.id,
            position=len(meal.candidates) + 1,
        )
    )
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def remove_candidate(
    session: AsyncSession, meal: MealEvent, actor_id: uuid.UUID, candidate_id: uuid.UUID
) -> MealEvent:
    """Remove an unvoted candidate before public voting.

    在公開投票開始前移除候選餐廳。
    """
    if meal.host_user_id != actor_id:
        raise PermissionError("meal host required")
    if (
        meal.visibility != "public"
        or meal.status not in ("open", "awaiting_host_decision")
        or meal.decided_restaurant_id is not None
    ):
        raise ValueError("candidates can only be edited before public voting starts")
    candidate = next((item for item in meal.candidates if item.id == candidate_id), None)
    if candidate is None:
        raise LookupError("candidate not found")
    await session.delete(candidate)
    await session.flush()
    remaining = [item for item in meal.candidates if item.id != candidate_id]
    for position, item in enumerate(remaining, start=1):
        item.position = position
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def join_meal(session: AsyncSession, meal: MealEvent, user_id: uuid.UUID) -> MealEvent:
    """Join a public meal or submit a private application.

    加入公開約飯或送出私人約飯申請。
    """
    await refresh_public_meal_state(session, meal)
    if meal.status != "open":
        raise ValueError("meal is no longer accepting members")
    if meal.host_user_id == user_id:
        raise ValueError("host is already a member")
    existing = membership_for(meal, user_id)
    if existing and existing.membership_status in FORMAL_MEMBERSHIP_STATUSES:
        raise ValueError("already a member")
    if existing and existing.membership_status == "pending":
        # Repeated private applications must fail closed instead of looking successful.
        # 私人約飯待審核期間不可重複送出申請，避免前端狀態異常或重複操作。
        raise ValueError("application is already pending")
    if len(formal_members(meal)) >= meal.capacity:
        raise ValueError("meal is full")

    next_status = "member" if meal.visibility == "public" else "pending"
    if existing:
        existing.membership_status = next_status
    else:
        session.add(
            MealMembership(
                meal_event_id=meal.id,
                user_id=user_id,
                membership_status=next_status,
            )
        )
    await session.commit()
    refreshed = (await get_meal(session, meal.id)) or meal
    await refresh_public_meal_state(session, refreshed)
    return (await get_meal(session, meal.id)) or refreshed


async def leave_meal(session: AsyncSession, meal: MealEvent, user_id: uuid.UUID) -> MealEvent:
    """Let a non-host member withdraw / 允許非發起人成員退出約飯。"""
    if meal.status not in LIVE_MEAL_STATUSES:
        raise ValueError("meal is no longer active")
    member = membership_for(meal, user_id)
    if member is None or member.membership_status not in (*FORMAL_MEMBERSHIP_STATUSES, "pending"):
        raise ValueError("active meal membership required")
    if member.membership_status == "host":
        raise ValueError("host cannot leave this meal")
    member.membership_status = "left"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def cancel_meal(session: AsyncSession, meal: MealEvent, host_id: uuid.UUID) -> MealEvent:
    """Soft-cancel a host-owned meal before its result is decided.

    只允許發起人在投票前或投票中解除約飯，保留資料供稽核與後續通知使用。
    """
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    if meal.status not in (*LIVE_MEAL_STATUSES,):
        raise ValueError("only unfinished meals can be cancelled")
    meal.status = "cancelled"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def review_member(
    session: AsyncSession,
    meal: MealEvent,
    host_id: uuid.UUID,
    target_user_id: uuid.UUID,
    approved: bool,
) -> MealEvent:
    """Approve or reject a private applicant / 審核私人約飯申請。"""
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    if meal.visibility != "private" or meal.status != "open":
        raise ValueError("private applications are not available")
    member = membership_for(meal, target_user_id)
    if member is None or member.membership_status != "pending":
        raise LookupError("pending applicant not found")
    if approved and len(formal_members(meal)) >= meal.capacity:
        raise ValueError("meal is full")
    member.membership_status = "member" if approved else "rejected"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def remove_member(
    session: AsyncSession, meal: MealEvent, host_id: uuid.UUID, target_user_id: uuid.UUID
) -> MealEvent:
    """Remove a member and immediately revoke voting eligibility.

    移除成員並立即取消投票資格。
    """
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    member = membership_for(meal, target_user_id)
    if member is None or member.membership_status not in ("member", "pending"):
        raise LookupError("removable member not found")
    member.membership_status = "removed"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def start_voting(session: AsyncSession, meal: MealEvent, host_id: uuid.UUID) -> MealEvent:
    """Allow a host to open a valid public ballot early.

    允許發起人提前開始公開投票。
    """
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    if (
        meal.visibility != "public"
        or meal.status != "open"
        or meal.decided_restaurant_id is not None
    ):
        raise ValueError("this meal cannot start voting")
    if not meal.candidates:
        raise ValueError("add at least one candidate before voting")
    meal.status = "voting"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def start_with_current_members(
    session: AsyncSession, meal: MealEvent, host_id: uuid.UUID
) -> MealEvent:
    """Let a host continue an undersubscribed public meal after its deadline.

    加入截止後未額滿但已有兩人的公開飯局，由發起人確認以現有人數開始。
    """
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    if meal.visibility != "public" or meal.status != "awaiting_host_decision":
        raise ValueError("this meal is not waiting for a host decision")
    if len(formal_members(meal)) < 2:
        raise ValueError("at least two members are required to start")
    if meal.decided_restaurant_id is not None:
        meal.status = "decided"
    elif meal.candidates:
        meal.status = "voting"
    else:
        raise ValueError("add at least one candidate before starting")
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def cast_vote(
    session: AsyncSession, meal: MealEvent, voter_id: uuid.UUID, candidate_id: uuid.UUID
) -> MealEvent:
    """Store one replaceable ballot for a formal member.

    儲存正式成員的一張可更新選票。
    """
    if meal.visibility != "public" or meal.status != "voting":
        raise ValueError("voting is not open")
    member = membership_for(meal, voter_id)
    if member is None or member.membership_status not in FORMAL_MEMBERSHIP_STATUSES:
        raise PermissionError("formal membership required to vote")
    if not any(candidate.id == candidate_id for candidate in meal.candidates):
        raise LookupError("candidate not found")
    vote = await session.scalar(
        select(MealVote).where(
            MealVote.meal_event_id == meal.id, MealVote.voter_user_id == voter_id
        )
    )
    if vote is None:
        session.add(
            MealVote(
                meal_event_id=meal.id,
                voter_user_id=voter_id,
                candidate_id=candidate_id,
            )
        )
    else:
        vote.candidate_id = candidate_id
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


async def finalize_vote(session: AsyncSession, meal: MealEvent, host_id: uuid.UUID) -> MealEvent:
    """Choose the leading restaurant, drawing only among ties.

    在最高票平手候選中隨機抽出結果。
    """
    if meal.host_user_id != host_id:
        raise PermissionError("meal host required")
    if meal.visibility != "public" or meal.status != "voting":
        raise ValueError("voting is not ready to finalize")
    formal_ids = [member.user_id for member in formal_members(meal)]
    vote_rows = (
        await session.execute(
            select(MealVote.candidate_id, func.count(MealVote.voter_user_id))
            .where(MealVote.meal_event_id == meal.id, MealVote.voter_user_id.in_(formal_ids))
            .group_by(MealVote.candidate_id)
        )
    ).all()
    counts = {candidate.id: 0 for candidate in meal.candidates}
    counts.update({candidate_id: int(count) for candidate_id, count in vote_rows})
    highest = max(counts.values(), default=0)
    if highest == 0:
        raise ValueError("at least one vote is required before finalizing")
    tied_candidate_ids = [
        candidate_id for candidate_id, count in counts.items() if count == highest
    ]
    winner_id = random.SystemRandom().choice(tied_candidate_ids)
    winner = next(candidate for candidate in meal.candidates if candidate.id == winner_id)
    meal.decided_restaurant_id = winner.restaurant_id
    meal.status = "decided"
    await session.commit()
    return (await get_meal(session, meal.id)) or meal


def restaurant_response(restaurant: Restaurant) -> MealRestaurantResponse:
    return MealRestaurantResponse(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        cuisine_name=restaurant.primary_cuisine.display_name
        if restaurant.primary_cuisine
        else None,
        photo_url=restaurant.photos[0].url if restaurant.photos else None,
    )


async def meal_response(
    session: AsyncSession, meal: MealEvent, current_user_id: uuid.UUID
) -> MealResponse:
    """Build one response from active member and ballot state.

    用有效成員與選票狀態組成單一回應。
    """
    active_members = formal_members(meal)
    can_manage = meal.host_user_id == current_user_id
    member_ids = [member.user_id for member in active_members]
    profile_member_ids = [
        member.user_id
        for member in meal.memberships
        if member.membership_status in FORMAL_MEMBERSHIP_STATUSES
        or (can_manage and meal.visibility == "private" and member.membership_status == "pending")
    ]
    meal_counts: dict[uuid.UUID, int] = {}
    if profile_member_ids:
        count_rows = (
            await session.execute(
                select(MealMembership.user_id, func.count(MealMembership.meal_event_id))
                .where(
                    MealMembership.user_id.in_(profile_member_ids),
                    MealMembership.membership_status.in_(FORMAL_MEMBERSHIP_STATUSES),
                )
                .group_by(MealMembership.user_id)
            )
        ).all()
        meal_counts = {user_id: int(count) for user_id, count in count_rows}

    vote_counts = {candidate.id: 0 for candidate in meal.candidates}
    if meal.candidates and member_ids:
        vote_rows = (
            await session.execute(
                select(MealVote.candidate_id, func.count(MealVote.voter_user_id))
                .where(MealVote.meal_event_id == meal.id, MealVote.voter_user_id.in_(member_ids))
                .group_by(MealVote.candidate_id)
            )
        ).all()
        vote_counts.update({candidate_id: int(count) for candidate_id, count in vote_rows})

    def member_response(
        member: MealMembership, include_private_profile: bool = False
    ) -> MealMemberResponse:
        profile = member.user.profile
        return MealMemberResponse(
            user_id=member.user_id,
            display_name=(profile.display_name if profile else member.user.email.split("@", 1)[0]),
            avatar_url=avatar_url_for_profile(profile) if profile else None,
            tags=[tag.display_name for tag in profile.tags] if profile else [],
            bio=profile.bio if include_private_profile and profile else None,
            meal_count=meal_counts.get(member.user_id) if include_private_profile else None,
            membership_status=cast(MealMembershipStatus, member.membership_status),
        )

    mine = membership_for(meal, current_user_id)
    can_view_candidates = meal.visibility == "public" or (
        mine is not None and mine.membership_status in FORMAL_MEMBERSHIP_STATUSES
    )
    can_view_vote_counts = (
        can_view_candidates
        and meal.status == "voting"
        and mine is not None
        and mine.membership_status in FORMAL_MEMBERSHIP_STATUSES
    )
    visible_members: Iterable[MealMembership] = active_members
    if can_manage and meal.visibility == "private":
        visible_members = [
            member
            for member in meal.memberships
            if member.membership_status in (*FORMAL_MEMBERSHIP_STATUSES, "pending")
        ]
    host_member = next(member for member in meal.memberships if member.membership_status == "host")
    my_vote = None
    if can_view_candidates:
        my_vote = await session.scalar(
            select(MealVote.candidate_id).where(
                MealVote.meal_event_id == meal.id, MealVote.voter_user_id == current_user_id
            )
        )
    return MealResponse(
        id=meal.id,
        visibility=cast(MealVisibility, meal.visibility),
        title=meal.title,
        description=meal.description,
        scheduled_at=meal.scheduled_at,
        join_deadline=meal.join_deadline,
        capacity=meal.capacity,
        status=cast(MealStatus, meal.status),
        host=member_response(host_member, include_private_profile=can_manage),
        members=[
            member_response(member, include_private_profile=can_manage)
            for member in visible_members
        ],
        member_count=len(active_members),
        candidates=[
            MealCandidateResponse(
                id=candidate.id,
                position=candidate.position,
                restaurant=restaurant_response(candidate.restaurant),
                # Vote totals are membership data, not public discovery data.
                # 投票總數只提供正式成員，公開瀏覽者只能看到候選店家。
                vote_count=(vote_counts[candidate.id] if can_view_vote_counts else None),
            )
            # Private candidates stay server-side until the applicant becomes a formal member.
            # 私人約飯申請通過前，候選餐廳不進入 API 回應，不能只靠前端隱藏。
            for candidate in meal.candidates
            if can_view_candidates
        ],
        decided_restaurant=(
            restaurant_response(meal.decided_restaurant) if meal.decided_restaurant else None
        ),
        my_membership_status=(cast(MealMembershipStatus, mine.membership_status) if mine else None),
        my_vote_candidate_id=my_vote,
        can_join=(
            meal.status == "open"
            and meal.host_user_id != current_user_id
            and (
                mine is None
                or mine.membership_status not in (*FORMAL_MEMBERSHIP_STATUSES, "pending")
            )
            and len(active_members) < meal.capacity
        ),
        can_vote=can_view_vote_counts,
        can_manage=can_manage,
    )
