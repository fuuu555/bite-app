"""Stage 1 API contracts / Stage 1 API 資料契約。"""

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


class MapRestaurantsResponse(BaseModel):
    """Bounded map query result / 有界地圖查詢結果。"""

    status: Literal["ok", "zoom_required"]
    restaurants: list[MapRestaurantResponse]
