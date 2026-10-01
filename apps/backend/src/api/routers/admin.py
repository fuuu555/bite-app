"""Administrator-only endpoints / 僅限管理員使用的端點。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.config import get_settings
from api.core.database import get_session
from api.core.security import (
    create_admin_session,
    require_admin,
    revoke_admin_session,
    set_admin_session_cookie,
    verify_password,
)
from api.domain.models import (
    AvatarAsset,
    Cuisine,
    Restaurant,
    RestaurantMenu,
    RestaurantPhoto,
    User,
)
from api.domain.schemas import (
    AdminLoginRequest,
    AdminUserResponse,
    AvatarAssetResponse,
    AvatarAssetUpdate,
    CuisineCreate,
    CuisineResponse,
    CuisineUpdate,
    GeocodeRequest,
    GeocodeResponse,
    RestaurantCreate,
    RestaurantMenuCreate,
    RestaurantMenuResponse,
    RestaurantMenuUpdate,
    RestaurantPhotoCreate,
    RestaurantPhotoResponse,
    RestaurantPhotoUpdate,
    RestaurantResponse,
    RestaurantUpdate,
    ReverseGeocodeRequest,
)
from api.integrations.geocoding import GeocodingProvider, get_geocoding_provider
from api.services.admin import (
    change_restaurant_status,
    create_restaurant,
    get_restaurant,
    restaurant_response,
    update_restaurant,
)
from api.services.avatar_assets import create_avatar_asset
from api.services.profile import avatar_asset_response
from api.services.restaurant_content import (
    create_menu,
    create_photo,
    delete_menu,
    delete_photo,
    list_menus,
    list_photos,
    update_menu,
    update_photo,
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
    result = await session.execute(
        select(User).where(User.email == payload.email, User.role == "admin")
    )
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


@router.get("/avatar-assets", response_model=list[AvatarAssetResponse])
async def list_avatar_assets(_: AdminDep, session: SessionDep) -> list[AvatarAssetResponse]:
    """List every avatar asset so admins can manage activation / 列出全部頭貼供管理員管理。"""
    result = await session.execute(
        select(AvatarAsset).order_by(AvatarAsset.is_active.desc(), AvatarAsset.display_name)
    )
    return [avatar_asset_response(asset) for asset in result.scalars()]


@router.post(
    "/avatar-assets",
    response_model=AvatarAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_avatar_asset(
    display_name: Annotated[str, Form(min_length=1, max_length=80)],
    file: Annotated[UploadFile, File(...)],
    admin: AdminDep,
    session: SessionDep,
) -> AvatarAssetResponse:
    """Upload one local avatar asset / 上傳一個本地頭貼資產。"""
    try:
        asset = await create_avatar_asset(session, admin, file, display_name)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return avatar_asset_response(asset)


@router.patch("/avatar-assets/{asset_id}", response_model=AvatarAssetResponse)
async def update_avatar_asset(
    asset_id: uuid.UUID,
    payload: AvatarAssetUpdate,
    _: AdminDep,
    session: SessionDep,
) -> AvatarAssetResponse:
    """Rename or deactivate an avatar without deleting referenced files.

    可重新命名或停用頭貼，不直接刪除仍被使用的檔案。
    """
    asset = await session.get(AvatarAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="avatar asset not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    await session.commit()
    await session.refresh(asset)
    return avatar_asset_response(asset)


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
    return restaurant_response(await change_restaurant_status(session, admin, restaurant, "draft"))


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


@router.get(
    "/restaurants/{restaurant_id}/menus",
    response_model=list[RestaurantMenuResponse],
)
async def list_restaurant_menus(
    restaurant_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> list[RestaurantMenu]:
    return await list_menus(session, restaurant_id)


@router.post(
    "/restaurants/{restaurant_id}/menus",
    response_model=RestaurantMenuResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_restaurant_menu(
    restaurant_id: uuid.UUID,
    payload: RestaurantMenuCreate,
    _: AdminDep,
    session: SessionDep,
) -> RestaurantMenu:
    return await create_menu(session, restaurant_id, payload)


@router.patch(
    "/restaurants/{restaurant_id}/menus/{menu_id}",
    response_model=RestaurantMenuResponse,
)
async def patch_restaurant_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    payload: RestaurantMenuUpdate,
    _: AdminDep,
    session: SessionDep,
) -> RestaurantMenu:
    return await update_menu(session, restaurant_id, menu_id, payload)


@router.delete(
    "/restaurants/{restaurant_id}/menus/{menu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_restaurant_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> None:
    await delete_menu(session, restaurant_id, menu_id)


@router.get(
    "/restaurants/{restaurant_id}/photos",
    response_model=list[RestaurantPhotoResponse],
)
async def list_restaurant_photos(
    restaurant_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> list[RestaurantPhoto]:
    return await list_photos(session, restaurant_id)


@router.post(
    "/restaurants/{restaurant_id}/photos",
    response_model=RestaurantPhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_restaurant_photo(
    restaurant_id: uuid.UUID,
    payload: RestaurantPhotoCreate,
    _: AdminDep,
    session: SessionDep,
) -> RestaurantPhoto:
    return await create_photo(session, restaurant_id, payload)


@router.patch(
    "/restaurants/{restaurant_id}/photos/{photo_id}",
    response_model=RestaurantPhotoResponse,
)
async def patch_restaurant_photo(
    restaurant_id: uuid.UUID,
    photo_id: uuid.UUID,
    payload: RestaurantPhotoUpdate,
    _: AdminDep,
    session: SessionDep,
) -> RestaurantPhoto:
    return await update_photo(session, restaurant_id, photo_id, payload)


@router.delete(
    "/restaurants/{restaurant_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_restaurant_photo(
    restaurant_id: uuid.UUID,
    photo_id: uuid.UUID,
    _: AdminDep,
    session: SessionDep,
) -> None:
    await delete_photo(session, restaurant_id, photo_id)


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
