"""Stage 1 domain services / Stage 1 領域服務。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import AuditLog, AuditLogChange, Cuisine, Restaurant, User
from api.schemas import CuisineResponse, RestaurantCreate, RestaurantResponse, RestaurantUpdate


def restaurant_snapshot(restaurant: Restaurant) -> dict[str, Any]:
    """Capture only auditable business fields / 僅記錄需稽核的業務欄位。"""
    return {
        "name": restaurant.name,
        "address": restaurant.address,
        "menu_url": restaurant.menu_url,
        "primary_cuisine_id": str(restaurant.primary_cuisine_id)
        if restaurant.primary_cuisine_id
        else None,
        "price_range": restaurant.price_range,
        "status": restaurant.status,
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
    }


async def add_audit_log(
    session: AsyncSession,
    actor: User,
    restaurant: Restaurant,
    action: str,
    before: dict[str, Any] | None,
) -> None:
    audit_log = AuditLog(
        actor_user_id=actor.id,
        entity_type="restaurant",
        entity_id=restaurant.id,
        action=action,
    )
    session.add(audit_log)
    await session.flush()

    before_values = before or {}
    after_values = restaurant_snapshot(restaurant)
    for field_name in sorted(before_values.keys() | after_values.keys()):
        before_value = before_values.get(field_name)
        after_value = after_values.get(field_name)
        if before_value == after_value:
            continue
        session.add(
            AuditLogChange(
                audit_log_id=audit_log.id,
                field_name=field_name,
                before_value=None if before_value is None else str(before_value),
                after_value=None if after_value is None else str(after_value),
            )
        )


async def require_active_cuisine(
    session: AsyncSession, cuisine_id: uuid.UUID | None
) -> Cuisine | None:
    if cuisine_id is None:
        return None
    cuisine = await session.get(Cuisine, cuisine_id)
    if cuisine is None or not cuisine.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid cuisine",
        )
    return cuisine


def validate_coordinates(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="latitude and longitude must be provided together",
        )
    if latitude is not None and not -90 <= latitude <= 90:
        raise HTTPException(status_code=422, detail="latitude is outside the valid range")
    if longitude is not None and not -180 <= longitude <= 180:
        raise HTTPException(status_code=422, detail="longitude is outside the valid range")


async def create_restaurant(
    session: AsyncSession, actor: User, payload: RestaurantCreate
) -> Restaurant:
    validate_coordinates(payload.latitude, payload.longitude)
    await require_active_cuisine(session, payload.primary_cuisine_id)
    restaurant = Restaurant(**payload.model_dump(), status="draft", source_type="manual")
    session.add(restaurant)
    await session.flush()
    await add_audit_log(session, actor, restaurant, "created", None)
    await session.commit()
    return await get_restaurant(session, restaurant.id)


async def get_restaurant(session: AsyncSession, restaurant_id: uuid.UUID) -> Restaurant:
    result = await session.execute(
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine))
        .where(Restaurant.id == restaurant_id)
    )
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise HTTPException(status_code=404, detail="restaurant not found")
    return restaurant


async def update_restaurant(
    session: AsyncSession,
    actor: User,
    restaurant: Restaurant,
    payload: RestaurantUpdate,
) -> Restaurant:
    values = payload.model_dump(exclude_unset=True)
    validate_coordinates(
        values.get("latitude", restaurant.latitude),
        values.get("longitude", restaurant.longitude),
    )
    if "primary_cuisine_id" in values:
        await require_active_cuisine(session, values["primary_cuisine_id"])
    before = restaurant_snapshot(restaurant)
    coordinate_changed = any(key in values for key in ("latitude", "longitude"))
    for field, value in values.items():
        setattr(restaurant, field, value)
    await session.flush()
    await add_audit_log(
        session,
        actor,
        restaurant,
        "coordinates_updated" if coordinate_changed else "updated",
        before,
    )
    await session.commit()
    return await get_restaurant(session, restaurant.id)


async def change_restaurant_status(
    session: AsyncSession,
    actor: User,
    restaurant: Restaurant,
    target_status: str,
) -> Restaurant:
    if target_status == "published":
        missing = [
            label
            for label, value in (
                (
                    "coordinates",
                    restaurant.latitude is not None and restaurant.longitude is not None,
                ),
                ("primary_cuisine", restaurant.primary_cuisine_id is not None),
                ("price_range", restaurant.price_range is not None),
            )
            if not value
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "restaurant_not_publishable", "missing": missing},
            )
        await require_active_cuisine(session, restaurant.primary_cuisine_id)

    before = restaurant_snapshot(restaurant)
    restaurant.status = target_status
    await session.flush()
    await add_audit_log(session, actor, restaurant, target_status, before)
    await session.commit()
    return await get_restaurant(session, restaurant.id)


def restaurant_response(restaurant: Restaurant) -> RestaurantResponse:
    return RestaurantResponse(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        menu_url=restaurant.menu_url,
        primary_cuisine_id=restaurant.primary_cuisine_id,
        primary_cuisine=(
            CuisineResponse.model_validate(restaurant.primary_cuisine)
            if restaurant.primary_cuisine
            else None
        ),
        price_range=restaurant.price_range,  # type: ignore[arg-type]
        status=restaurant.status,  # type: ignore[arg-type]
        source_type=restaurant.source_type,  # type: ignore[arg-type]
        latitude=restaurant.latitude,
        longitude=restaurant.longitude,
        created_at=restaurant.created_at,
        updated_at=restaurant.updated_at,
    )
