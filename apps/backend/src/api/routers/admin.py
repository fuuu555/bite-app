"""Administrator-only Stage 1 endpoints / 僅限管理員的 Stage 1 端點。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.config import get_settings
from api.db import get_session
from api.geocoding import GeocodingProvider, get_geocoding_provider
from api.models import Cuisine, Restaurant, User
from api.schemas import (
    AdminLoginRequest,
    AdminUserResponse,
    CuisineCreate,
    CuisineResponse,
    CuisineUpdate,
    GeocodeRequest,
    GeocodeResponse,
    RestaurantCreate,
    RestaurantResponse,
    RestaurantUpdate,
    ReverseGeocodeRequest,
)
from api.security import (
    create_admin_session,
    require_admin,
    revoke_admin_session,
    set_admin_session_cookie,
    verify_password,
)
from api.services import (
    change_restaurant_status,
    create_restaurant,
    get_restaurant,
    restaurant_response,
    update_restaurant,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(require_admin)]
SessionCookie = Annotated[str | None, Cookie(alias="bitemap_admin_session")]
GeocodingDep = Annotated[GeocodingProvider, Depends(get_geocoding_provider)]


@router.post("/session", response_model=AdminUserResponse)
async def login(
    payload: AdminLoginRequest,
    response: Response,
    session: SessionDep,
) -> AdminUserResponse:
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or user.role != "admin"
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = await create_admin_session(session, user)
    set_admin_session_cookie(response, token)
    return AdminUserResponse(id=user.id, email=user.email, role=user.role)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    session_token: SessionCookie = None,
) -> None:
    await revoke_admin_session(session, session_token)
    response.delete_cookie(get_settings().admin_session_cookie, path="/")


@router.get("/me", response_model=AdminUserResponse)
async def current_admin(admin: AdminDep) -> AdminUserResponse:
    return AdminUserResponse(id=admin.id, email=admin.email, role=admin.role)


@router.get("/cuisines", response_model=list[CuisineResponse])
async def list_cuisines(_: AdminDep, session: SessionDep) -> list[Cuisine]:
    result = await session.execute(select(Cuisine).order_by(Cuisine.display_name))
    return list(result.scalars())


@router.post("/cuisines", response_model=CuisineResponse, status_code=status.HTTP_201_CREATED)
async def create_cuisine(
    payload: CuisineCreate,
    _: AdminDep,
    session: SessionDep,
) -> Cuisine:
    cuisine = Cuisine(**payload.model_dump())
    session.add(cuisine)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="cuisine slug already exists") from error
    await session.refresh(cuisine)
    return cuisine


@router.patch("/cuisines/{cuisine_id}", response_model=CuisineResponse)
async def update_cuisine(
    cuisine_id: uuid.UUID,
    payload: CuisineUpdate,
    _: AdminDep,
    session: SessionDep,
) -> Cuisine:
    cuisine = await session.get(Cuisine, cuisine_id)
    if cuisine is None:
        raise HTTPException(status_code=404, detail="cuisine not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cuisine, field, value)
    await session.commit()
    await session.refresh(cuisine)
    return cuisine


@router.delete("/cuisines/{cuisine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cuisine(
    cuisine_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> None:
    try:
        result = await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise HTTPException(status_code=404, detail="cuisine not found")
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="cuisine is used by a restaurant") from error


@router.get("/restaurants", response_model=list[RestaurantResponse])
async def list_restaurants(_: AdminDep, session: SessionDep) -> list[RestaurantResponse]:
    result = await session.execute(
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine))
        .order_by(Restaurant.updated_at.desc())
    )
    return [restaurant_response(item) for item in result.scalars()]


@router.post("/restaurants", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant_endpoint(
    payload: RestaurantCreate,
    admin: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    return restaurant_response(await create_restaurant(session, admin, payload))


@router.get("/restaurants/{restaurant_id}", response_model=RestaurantResponse)
async def read_restaurant(
    restaurant_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    return restaurant_response(await get_restaurant(session, restaurant_id))


@router.patch("/restaurants/{restaurant_id}", response_model=RestaurantResponse)
async def patch_restaurant(
    restaurant_id: uuid.UUID,
    payload: RestaurantUpdate,
    admin: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    restaurant = await get_restaurant(session, restaurant_id)
    return restaurant_response(await update_restaurant(session, admin, restaurant, payload))


@router.post("/restaurants/{restaurant_id}/publish", response_model=RestaurantResponse)
async def publish_restaurant(
    restaurant_id: uuid.UUID,
    admin: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    restaurant = await get_restaurant(session, restaurant_id)
    return restaurant_response(
        await change_restaurant_status(session, admin, restaurant, "published")
    )


@router.post("/restaurants/{restaurant_id}/archive", response_model=RestaurantResponse)
async def archive_restaurant(
    restaurant_id: uuid.UUID,
    admin: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    restaurant = await get_restaurant(session, restaurant_id)
    return restaurant_response(
        await change_restaurant_status(session, admin, restaurant, "archived")
    )


@router.post("/restaurants/{restaurant_id}/restore", response_model=RestaurantResponse)
async def restore_restaurant(
    restaurant_id: uuid.UUID,
    admin: AdminDep,
    session: SessionDep,
) -> RestaurantResponse:
    """Restore an archived restaurant to an editable draft / 將封存店家解封為草稿。"""
    restaurant = await get_restaurant(session, restaurant_id)
    return restaurant_response(
        await change_restaurant_status(session, admin, restaurant, "draft")
    )


@router.delete("/restaurants/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant(
    restaurant_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> None:
    """Permanently delete a restaurant / 永久刪除店家資料。"""
    result = await session.execute(delete(Restaurant).where(Restaurant.id == restaurant_id))
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="restaurant not found")
    await session.commit()


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(
    payload: GeocodeRequest,
    _: AdminDep,
    provider: GeocodingDep,
) -> GeocodeResponse:
    if not provider.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "geocoding_not_configured", "manual_map_selection": True},
        )
    return GeocodeResponse(configured=True, candidates=await provider.geocode(payload.address))


@router.post("/geocode/reverse")
async def reverse_geocode(
    payload: ReverseGeocodeRequest,
    _: AdminDep,
    provider: GeocodingDep,
) -> dict[str, str | None]:
    if not provider.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "geocoding_not_configured"},
        )
    return {"address": await provider.reverse(payload.latitude, payload.longitude)}
