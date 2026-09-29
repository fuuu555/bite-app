"""Restaurant menu and photo administration / 餐廳菜單與照片管理服務。"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.models import Restaurant, RestaurantMenu, RestaurantPhoto
from api.domain.schemas import (
    RestaurantMenuCreate,
    RestaurantMenuUpdate,
    RestaurantPhotoCreate,
    RestaurantPhotoUpdate,
)


async def require_restaurant(session: AsyncSession, restaurant_id: uuid.UUID) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="restaurant not found")
    return restaurant


async def list_menus(session: AsyncSession, restaurant_id: uuid.UUID) -> list[RestaurantMenu]:
    await require_restaurant(session, restaurant_id)
    result = await session.execute(
        select(RestaurantMenu)
        .where(RestaurantMenu.restaurant_id == restaurant_id)
        .order_by(RestaurantMenu.created_at, RestaurantMenu.id)
    )
    return list(result.scalars())


async def create_menu(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    payload: RestaurantMenuCreate,
) -> RestaurantMenu:
    await require_restaurant(session, restaurant_id)
    menu = RestaurantMenu(restaurant_id=restaurant_id, **payload.model_dump())
    session.add(menu)
    await session.commit()
    await session.refresh(menu)
    return menu


async def update_menu(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    payload: RestaurantMenuUpdate,
) -> RestaurantMenu:
    await require_restaurant(session, restaurant_id)
    menu = await session.scalar(
        select(RestaurantMenu).where(
            RestaurantMenu.id == menu_id,
            RestaurantMenu.restaurant_id == restaurant_id,
        )
    )
    if menu is None:
        raise HTTPException(status_code=404, detail="menu not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(menu, field, value)
    await session.commit()
    await session.refresh(menu)
    return menu


async def delete_menu(session: AsyncSession, restaurant_id: uuid.UUID, menu_id: uuid.UUID) -> None:
    await require_restaurant(session, restaurant_id)
    result = await session.execute(
        delete(RestaurantMenu).where(
            RestaurantMenu.id == menu_id,
            RestaurantMenu.restaurant_id == restaurant_id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="menu not found")
    await session.commit()


async def list_photos(session: AsyncSession, restaurant_id: uuid.UUID) -> list[RestaurantPhoto]:
    await require_restaurant(session, restaurant_id)
    result = await session.execute(
        select(RestaurantPhoto)
        .where(RestaurantPhoto.restaurant_id == restaurant_id)
        .order_by(RestaurantPhoto.sort_order, RestaurantPhoto.created_at, RestaurantPhoto.id)
    )
    return list(result.scalars())


async def create_photo(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    payload: RestaurantPhotoCreate,
) -> RestaurantPhoto:
    await require_restaurant(session, restaurant_id)
    photo = RestaurantPhoto(restaurant_id=restaurant_id, **payload.model_dump())
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def update_photo(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    photo_id: uuid.UUID,
    payload: RestaurantPhotoUpdate,
) -> RestaurantPhoto:
    await require_restaurant(session, restaurant_id)
    photo = await session.scalar(
        select(RestaurantPhoto).where(
            RestaurantPhoto.id == photo_id,
            RestaurantPhoto.restaurant_id == restaurant_id,
        )
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    await session.commit()
    await session.refresh(photo)
    return photo


async def delete_photo(
    session: AsyncSession, restaurant_id: uuid.UUID, photo_id: uuid.UUID
) -> None:
    await require_restaurant(session, restaurant_id)
    result = await session.execute(
        delete(RestaurantPhoto).where(
            RestaurantPhoto.id == photo_id,
            RestaurantPhoto.restaurant_id == restaurant_id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="photo not found")
    await session.commit()
