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


TourismImportStatus = Literal["running", "succeeded", "failed"]


class TourismImportStartResponse(BaseModel):
    status: Literal["started", "already_running"]
    datasets: list[TourismSourceDataset]


class TourismImportRunResponse(BaseModel):
    id: uuid.UUID
    source_dataset: TourismSourceDataset
    source_url: str
    status: TourismImportStatus
    started_at: datetime
    completed_at: datetime | None
    downloaded_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    invalid_count: int
    deactivated_count: int
    error_message: str | None


class AvatarAssetResponse(BaseModel):
    """Selectable avatar metadata / 可選頭貼中繼資料。"""

    id: uuid.UUID
    display_name: str
    url: str
    mime_type: str
    file_size: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AvatarAssetUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_avatar_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value).strip()
        return normalized or None


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


RelationshipStatus = Literal[
    "self",
    "none",
    "friends",
    "outgoing_pending",
    "incoming_pending",
    "blocked_by_me",
    "blocked_me",
]


class RelationshipStateResponse(BaseModel):
    status: RelationshipStatus
    request_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    can_message: bool = False
    can_add_friend: bool = False
    can_accept_friend_request: bool = False
    follow_status: Literal["none", "following", "followed_by", "mutual"] = "none"


class PublicProfileResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    bio: str | None
    avatar_url: str | None
    avatar_source: Literal["builtin", "google", "url"]
    avatar_asset_id: uuid.UUID | None
    tags: list[ProfileTagResponse]
    accept_stranger_messages: bool = True
    relationship: RelationshipStateResponse | None = None


class MyProfileResponse(PublicProfileResponse):
    email: str
    friend_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class FriendSummaryResponse(BaseModel):
    """Minimal profile data shown in the friends hub / 好友頁顯示的最小個人資料。"""

    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    avatar_source: Literal["builtin", "google", "url"]
    avatar_asset_id: uuid.UUID | None
    conversation_id: uuid.UUID | None = None


class FriendLookupResponse(FriendSummaryResponse):
    """A friend-code result with current relationship state / 好友碼查詢結果。"""

    relationship: RelationshipStateResponse


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://[^\s]+$")
    avatar_asset_id: uuid.UUID | None = None
    tags: list[str] | None = Field(default=None, max_length=8)
    accept_stranger_messages: bool | None = None

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


FriendRequestStatus = Literal["pending", "accepted", "rejected", "cancelled"]


class FriendRequestResponse(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    recipient_id: uuid.UUID
    status: FriendRequestStatus
    created_at: datetime
    responded_at: datetime | None = None


class FriendRequestCreateRequest(BaseModel):
    user_id: uuid.UUID


class SocialActionResponse(BaseModel):
    relationship: RelationshipStateResponse
    request: FriendRequestResponse | None = None


class FollowSummaryResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    avatar_source: Literal["builtin", "google", "url"]
    avatar_asset_id: uuid.UUID | None
    created_at: datetime


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
    google_lookup_enabled: bool = True
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
    google_lookup_enabled: bool = True
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
    google_place_id: str | None
    google_lookup_enabled: bool
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


class MapQueryMetricResponse(BaseModel):
    occurred_at: datetime
    duration_ms: float
    result_count: int
    cache_hit: bool
    response_status: Literal["ok", "zoom_required", "error"]
    query_summary: str


class MapPerformanceMetricsResponse(BaseModel):
    window_minutes: int
    query_count: int
    average_duration_ms: float
    p95_duration_ms: float
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    zoom_required_count: int
    zoom_required_rate: float
    error_count: int
    error_rate: float
    published_restaurant_count: int
    cache_entries: int
    status: Literal["normal", "attention", "critical"]
    alerts: list[str]
    last_updated_at: datetime
    recent_queries: list[MapQueryMetricResponse]


class MapSearchResponse(BaseModel):
    """Published restaurant search results / 已發布店家搜尋結果。"""

    status: Literal["ok"]
    restaurants: list[MapRestaurantResponse]


TourismPlaceCategory = Literal["restaurant", "attraction", "hotel", "service_site"]
TourismSourceDataset = Literal["food", "attraction", "hotel", "service_site"]


class TourismPlaceResponse(BaseModel):
    """Public official tourism place payload / 公開官方觀光地點資料。"""

    id: uuid.UUID
    source_dataset: TourismSourceDataset
    source_record_id: str
    category: TourismPlaceCategory
    name: str
    description: str | None
    address: str | None
    phone: str | None
    latitude: float
    longitude: float
    official_url: str | None
    opening_hours: str | None
    source_updated_at: datetime | None
    tags: list[str]
    icon_key: str | None
    icon_classification_slug: str | None
    icon_color: str


class TourismAdminPlaceResponse(TourismPlaceResponse):
    """Admin view with source values and BiteMap conversion state."""

    official_name: str
    official_address: str | None
    official_icon_key: str
    is_map_enabled: bool
    linked_restaurant_id: uuid.UUID | None


class TourismPlaceUpdate(BaseModel):
    """Editable text fields for an official tourism place."""

    name: str | None = Field(default=None, min_length=1, max_length=240)
    address: str | None = Field(default=None, min_length=1, max_length=500)


class TourismPlacesEnableResponse(BaseModel):
    """Bulk map enable result."""

    enabled_count: int


class TourismPlaceConvertRequest(BaseModel):
    """Options used when promoting an official food place to BiteMap."""

    google_lookup_enabled: bool = False


class TourismAdminPlacesResponse(BaseModel):
    """Paged admin tourism place list."""

    places: list[TourismAdminPlaceResponse]
    total: int
    has_more: bool


class TourismDuplicatePairResponse(BaseModel):
    """Two official source records that may represent the same place."""

    left: TourismAdminPlaceResponse
    right: TourismAdminPlaceResponse
    name_similarity: float
    match_reasons: list[str]


class TourismDuplicatePairsResponse(BaseModel):
    """Paged candidate pairs for manual duplicate review."""

    pairs: list[TourismDuplicatePairResponse]
    total: int
    has_more: bool


class TourismPlaceDeleteResponse(BaseModel):
    """Result of permanently deleting an official source row."""

    deleted: bool


class TourismPlacesDeleteRequest(BaseModel):
    """Source row IDs to permanently delete in one transaction."""

    place_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @field_validator("place_ids")
    @classmethod
    def require_unique_place_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("place_ids must not contain duplicates")
        return value


class TourismPlacesDeleteResponse(BaseModel):
    """Result of an atomic permanent deletion of official source rows."""

    deleted_count: int
    deleted_ids: list[uuid.UUID]


class TourismPlacesResponse(BaseModel):
    """Bounded official tourism map results / 有界官方觀光地圖結果。"""

    places: list[TourismPlaceResponse]
    has_more: bool


ExploreSort = Literal[
    "recommended",
    "distance",
    "price",
    "revisit_rate",
    "google_rating",
    "trust",
    "stable",
]
ExploreDistanceKm = Literal[2, 5, 10]
ExploreTrustLevel = Literal["high", "medium", "low"]


class ExploreAppSignalsResponse(BaseModel):
    """App-owned signals kept separate from external ratings / App 自有指標。"""

    revisit_rate: float | None = None
    rating_count: int | None = None
    will_return_count: int | None = None
    neutral_count: int | None = None
    will_not_return_count: int | None = None
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


RevisitStatus = Literal["will_return", "neutral", "will_not_return"]
ReviewSort = Literal["featured", "latest", "popular"]
ReviewStatusFilter = Literal["all", "will_return", "neutral", "will_not_return"]


class ReviewReasonResponse(BaseModel):
    """Active review reason metadata / 啟用中的留言原因標籤。"""

    id: uuid.UUID
    slug: str
    display_name: str
    polarity: Literal["positive", "negative"]


class ReviewCreateRequest(BaseModel):
    """Create a review event / 建立一筆留言事件。"""

    content: str = Field(min_length=1, max_length=2000)
    revisit_status: RevisitStatus
    reason_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("content must be a string")
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("content cannot be empty")
        return normalized

    @field_validator("reason_ids")
    @classmethod
    def normalize_reason_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(value))


class ReviewUpdateRequest(BaseModel):
    """Editable review fields / 可編輯的留言欄位。"""

    content: str | None = Field(default=None, min_length=1, max_length=2000)
    revisit_status: RevisitStatus | None = None
    reason_ids: list[uuid.UUID] | None = Field(default=None, max_length=5)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("content must be a string")
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("content cannot be empty")
        return normalized

    @field_validator("reason_ids")
    @classmethod
    def normalize_reason_ids(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def require_change(self) -> ReviewUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be updated")
        return self


class ReviewResponse(BaseModel):
    """Public review event contract / 公開留言事件契約。"""

    id: uuid.UUID
    thread_id: uuid.UUID
    entry_number: int
    is_revisit: bool
    author_id: uuid.UUID
    author_display_name: str
    author_avatar_url: str | None
    content: str
    revisit_status: RevisitStatus
    reasons: list[ReviewReasonResponse]
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    is_deleted: bool
    revisit_count: int
    like_count: int
    liked_by_me: bool
    is_owner: bool


class ReviewListResponse(BaseModel):
    """Paged current review list / 最新留言列表契約。"""

    reviews: list[ReviewResponse]
    total: int
    sort: ReviewSort
    status: ReviewStatusFilter
    available_reasons: list[ReviewReasonResponse]
    has_current_user_review: bool


class ReviewTimelineResponse(BaseModel):
    """One user's visible revisit history / 單一使用者可見的再訪時間線。"""

    reviews: list[ReviewResponse]


class ProfileReviewResponse(BaseModel):
    """Current user's review history card / 使用者自己的留言紀錄卡片。"""

    id: uuid.UUID
    restaurant_id: uuid.UUID
    restaurant_name: str
    restaurant_photo_url: str | None
    entry_number: int
    is_revisit: bool
    content: str
    revisit_status: RevisitStatus
    reasons: list[ReviewReasonResponse]
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    revisit_count: int


class ProfileReviewListResponse(BaseModel):
    reviews: list[ProfileReviewResponse]
    total: int


class ReviewLikeResponse(BaseModel):
    liked: bool
    like_count: int


class FavoriteRestaurantResponse(BaseModel):
    """Favorite restaurant card contract / 收藏餐廳卡片契約。"""

    id: uuid.UUID
    name: str
    address: str
    primary_cuisine: MapCuisineResponse
    price_range: PriceRange
    menu_url: str | None
    photo_url: str | None = None
    created_at: datetime


class FavoriteListResponse(BaseModel):
    restaurants: list[FavoriteRestaurantResponse]
    total: int


class FavoriteStateResponse(BaseModel):
    favorited: bool


MealVisibility = Literal["public", "private"]
MealStatus = Literal[
    "open",
    "awaiting_host_decision",
    "voting",
    "decided",
    "cancelled",
    "completed",
]
MealMembershipStatus = Literal["host", "member", "pending", "rejected", "left", "removed"]
MealRestaurantMode = Literal["direct", "vote"]
PrivateMealCondition = Literal["male_only", "female_only"]


class MealCreateRequest(BaseModel):
    """The confirmed fields needed to create a Stage 7 meal / 建立 Stage 7 約飯所需欄位。"""

    visibility: MealVisibility
    private_condition: PrivateMealCondition | None = None
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    scheduled_at: datetime
    join_deadline: datetime | None = None
    capacity: int = Field(ge=2)
    restaurant_mode: MealRestaurantMode
    restaurant_id: uuid.UUID | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_meal_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("meal text must be a string")
        normalized = re.sub(r"\s+", " ", value).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_meal_choice(self) -> MealCreateRequest:
        if not self.title:
            raise ValueError("title cannot be empty")
        if self.restaurant_mode == "direct" and self.restaurant_id is None:
            raise ValueError("a direct meal needs a restaurant")
        if self.visibility == "public" and self.join_deadline is None:
            raise ValueError("a public meal needs a join deadline")
        if self.visibility == "public" and self.private_condition is not None:
            raise ValueError("public meals cannot have a private condition")
        return self


class MealCandidateCreateRequest(BaseModel):
    restaurant_id: uuid.UUID


class MealVoteRequest(BaseModel):
    candidate_id: uuid.UUID


class MealMemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None
    tags: list[str] = Field(default_factory=list)
    bio: str | None = None
    meal_count: int | None = None
    membership_status: MealMembershipStatus


class MealRestaurantResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    cuisine_name: str | None
    photo_url: str | None


class MealCandidateResponse(BaseModel):
    id: uuid.UUID
    position: int
    restaurant: MealRestaurantResponse
    vote_count: int | None


class MealResponse(BaseModel):
    """A meal card/detail contract with only live server-derived state / 約飯卡片與詳情契約。"""

    id: uuid.UUID
    visibility: MealVisibility
    private_condition: PrivateMealCondition | None
    title: str
    description: str | None
    scheduled_at: datetime
    join_deadline: datetime | None
    capacity: int
    status: MealStatus
    host: MealMemberResponse
    members: list[MealMemberResponse]
    member_count: int
    candidates: list[MealCandidateResponse]
    decided_restaurant: MealRestaurantResponse | None
    my_membership_status: MealMembershipStatus | None
    my_vote_candidate_id: uuid.UUID | None
    can_join: bool
    can_vote: bool
    can_manage: bool


class MealListResponse(BaseModel):
    meals: list[MealResponse]


class ChatAuthorResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None


class MessageReplyResponse(BaseModel):
    id: uuid.UUID
    sender: ChatAuthorResponse
    content: str
    is_recalled: bool = False


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    conversation_kind: Literal["meal", "direct"]
    meal_id: uuid.UUID | None = None
    sender: ChatAuthorResponse
    content: str
    created_at: datetime
    is_recalled: bool = False
    recalled_at: datetime | None = None
    can_recall: bool = False
    is_mine: bool = False
    reply_to: MessageReplyResponse | None = None
    is_pinned: bool = False
    pinned_at: datetime | None = None
    can_pin: bool = False


class ConversationReadRequest(BaseModel):
    message_id: uuid.UUID


class ConversationReadResponse(BaseModel):
    conversation_id: uuid.UUID
    meal_id: uuid.UUID | None = None
    message_id: uuid.UUID
    read_at: datetime


class MessagePageResponse(BaseModel):
    messages: list[MessageResponse]
    next_cursor: str | None


class PinnedMessagesResponse(BaseModel):
    messages: list[MessageResponse]


class ConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    kind: Literal["meal", "direct"]
    category: Literal["meal", "direct", "friends"]
    meal_id: uuid.UUID | None = None
    meal_title: str | None = None
    meal_status: MealStatus | None = None
    other_user: ChatAuthorResponse | None = None
    latest_message: MessageResponse | None
    unread_count: int = 0


class DirectConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    other_user: ChatAuthorResponse


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
