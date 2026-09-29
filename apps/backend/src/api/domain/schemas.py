"""Application API contracts / 應用程式 API 資料契約。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PriceRange = Literal["under_200", "200_to_400", "400_to_800", "over_800"]
RestaurantStatus = Literal["draft", "published", "archived"]


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["user"]


class ProfileTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    display_name: str
    is_system: bool


class PublicProfileResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    bio: str | None
    avatar_url: str | None
    tags: list[ProfileTagResponse]


class MyProfileResponse(PublicProfileResponse):
    email: str


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    tags: list[str] | None = Field(default=None, max_length=8)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        if value is None:
            raise ValueError("display_name cannot be null")
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("display_name cannot be empty")
        return normalized

    @field_validator("bio", mode="before")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value).strip()
        return normalized or None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("tags must be a list")
        normalized = [re.sub(r"\s+", " ", item).strip() for item in value]
        return list(dict.fromkeys(item for item in normalized if item))


class UserSessionResponse(BaseModel):
    id: uuid.UUID
    device_label: str
    expires_at: datetime
    last_seen_at: datetime
    created_at: datetime
    current: bool


class CuisineCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    icon_key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$")


class CuisineUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon_key: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$")
    is_active: bool | None = None


class CuisineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    display_name: str
    color: str
    icon_key: str
    is_active: bool


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=500)
    menu_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    primary_cuisine_id: uuid.UUID | None = None
    price_range: PriceRange | None = None
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> RestaurantCreate:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    menu_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    primary_cuisine_id: uuid.UUID | None = None
    price_range: PriceRange | None = None
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> RestaurantUpdate:
        fields = self.model_fields_set
        if ("latitude" in fields) != ("longitude" in fields):
            raise ValueError("latitude and longitude must be updated together")
        return self


class RestaurantResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    menu_url: str | None
    primary_cuisine_id: uuid.UUID | None
    primary_cuisine: CuisineResponse | None
    price_range: PriceRange | None
    status: RestaurantStatus
    source_type: Literal["manual"]
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime


class RestaurantMenuCreate(BaseModel):
    title: str = Field(default="菜單", min_length=1, max_length=160)
    url: str = Field(max_length=1000, pattern=r"^https?://[^\s]+$")
    last_updated_at: datetime | None = None


class RestaurantMenuUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    last_updated_at: datetime | None = None


class RestaurantMenuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    title: str
    url: str
    last_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RestaurantPhotoCreate(BaseModel):
    url: str = Field(max_length=1000, pattern=r"^https?://[^\s]+$")
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=1000)


class RestaurantPhotoUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    alt_text: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=1000)


class RestaurantPhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    url: str
    alt_text: str | None
    sort_order: int
    created_at: datetime


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=3, max_length=500)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()


class ReverseGeocodeRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class GeocodingCandidate(BaseModel):
    label: str
    latitude: float
    longitude: float


class GeocodeResponse(BaseModel):
    configured: bool
    candidates: list[GeocodingCandidate]


class MapCuisineResponse(BaseModel):
    """Cuisine metadata needed by public map markers / 公開地圖標記所需料理資料。"""

    id: uuid.UUID
    display_name: str
    color: str
    icon_key: str


class MapRestaurantResponse(BaseModel):
    """Minimal published restaurant payload / 公開地圖使用的最小店家資料。"""

    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    primary_cuisine: MapCuisineResponse
    price_range: PriceRange
    menu_url: str | None
    photo_url: str | None = None


class MapRestaurantsResponse(BaseModel):
    """Bounded map query result / 有界地圖查詢結果。"""

    status: Literal["ok", "zoom_required"]
    restaurants: list[MapRestaurantResponse]


class MapSearchLocationResponse(BaseModel):
    """External location candidate / 外部地區定位候選。"""

    label: str
    region: str | None = None
    latitude: float
    longitude: float
    source: str


class MapSearchResponse(BaseModel):
    """Grouped map search results / 分組的地圖搜尋結果。"""

    status: Literal["ok", "partial"]
    locations: list[MapSearchLocationResponse]
    restaurants: list[MapRestaurantResponse]


ExploreSort = Literal["stable"]
ExploreDistanceKm = Literal[2, 5, 10]
ExploreTrustLevel = Literal["high", "medium", "low"]


class ExploreAppSignalsResponse(BaseModel):
    """App-owned signals kept separate from external ratings / App 自有指標。"""

    revisit_rate: float | None = None
    rating_count: int | None = None
    trust_level: ExploreTrustLevel | None = None


class ExploreGoogleSignalsResponse(BaseModel):
    """Optional Google fields without merging them into App data / 獨立的 Google 指標。"""

    rating: float | None = None
    review_count: int | None = None


class ExploreRestaurantSummaryResponse(BaseModel):
    """Restaurant card contract shared by Top 3 and the full list / 探索店家卡契約。"""

    id: uuid.UUID
    name: str
    address: str
    primary_cuisine: MapCuisineResponse
    price_range: PriceRange
    menu_url: str | None
    photo_url: str | None = None
    distance_meters: float | None = None
    app: ExploreAppSignalsResponse = Field(default_factory=ExploreAppSignalsResponse)
    google: ExploreGoogleSignalsResponse = Field(default_factory=ExploreGoogleSignalsResponse)


class ExploreRestaurantsResponse(BaseModel):
    """One deterministic result source for Top 3 and the full list / 共用排序結果。"""

    status: Literal["ok"] = "ok"
    query: str | None
    sort: ExploreSort
    top_restaurants: list[ExploreRestaurantSummaryResponse]
    restaurants: list[ExploreRestaurantSummaryResponse]


class ExploreMenuResponse(BaseModel):
    """Menu skeleton using only currently stored data / 只使用現有資料的菜單骨架。"""

    url: str | None
    last_updated_at: datetime | None = None


class ExploreMenuDocumentResponse(BaseModel):
    """Published restaurant menu metadata / 公開餐廳菜單中繼資料。"""

    id: uuid.UUID
    title: str
    url: str
    last_updated_at: datetime | None = None


class ExplorePhotoResponse(BaseModel):
    """Published restaurant photo metadata without storage assumptions / 公開照片中繼資料。"""

    id: uuid.UUID
    url: str
    alt_text: str | None = None


class ExploreRestaurantDetailResponse(ExploreRestaurantSummaryResponse):
    """Two-layer restaurant detail contract / 餐廳兩層資訊契約。"""

    latitude: float | None
    longitude: float | None
    menu: ExploreMenuResponse
    menus: list[ExploreMenuDocumentResponse] = Field(default_factory=list)
    photos: list[ExplorePhotoResponse] = Field(default_factory=list)
