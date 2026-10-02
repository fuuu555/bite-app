"""Application persistence models / 應用程式資料庫模型。"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


def _default_friend_code() -> str:
    """Provide a valid ORM fallback for fixtures and direct model creation / 提供 ORM 預設碼。"""
    return f"{secrets.randbelow(1_000_000):06d}"


class User(Base):
    """Shared administrator and user identity / 共用管理員與一般使用者身分。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    identities: Mapped[list[UserIdentity]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserIdentity(Base):
    """External login identity / 外部登入提供者的身分對照。"""

    __tablename__ = "user_identities"
    __table_args__ = (
        CheckConstraint("provider IN ('google')", name="ck_user_identities_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="identities")


class AvatarAsset(Base):
    """Admin-managed local avatar asset / 管理員管理的本地頭貼資產。"""

    __tablename__ = "avatar_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    mime_type: Mapped[str] = mapped_column(String(80))
    file_size: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped[User | None] = relationship()


class UserProfile(Base):
    """User-owned public profile fields / 使用者可管理的公開個人資料。"""

    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "friend_code ~ '^[0-9]{6}$'",
            name="ck_user_profiles_friend_code_digits",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_source: Mapped[str] = mapped_column(String(16), default="url")
    avatar_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avatar_assets.id", ondelete="SET NULL"), nullable=True
    )
    friend_code: Mapped[str] = mapped_column(String(6), unique=True, default=_default_friend_code)
    accept_stranger_messages: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="profile")
    avatar_asset: Mapped[AvatarAsset | None] = relationship()
    tags: Mapped[list[ProfileTag]] = relationship(
        secondary="user_profile_tags",
        back_populates="profiles",
        order_by="ProfileTag.display_name",
    )


class ProfileTag(Base):
    """Reusable system or user-created food interest tag / 可重用的美食興趣標籤。"""

    __tablename__ = "profile_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(40))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profiles: Mapped[list[UserProfile]] = relationship(
        secondary="user_profile_tags",
        back_populates="tags",
    )


user_profile_tags = Table(
    "user_profile_tags",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("profile_tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class AdminSession(Base):
    """Revocable administrator session / 可撤銷的管理員 Session。"""

    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()


class UserSession(Base):
    """Revocable general-user session / 可撤銷的一般使用者 Session。"""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_label: Mapped[str] = mapped_column(String(160), default="瀏覽器")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()


class Cuisine(Base):
    """Cuisine marker metadata / 料理分類與地圖標記資料。"""

    __tablename__ = "cuisines"
    __table_args__ = (CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_cuisines_color_hex"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7))
    icon_key: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Restaurant(Base):
    """Restaurant master record / 店家主資料。"""

    __tablename__ = "restaurants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_restaurants_status",
        ),
        CheckConstraint("source_type IN ('manual')", name="ck_restaurants_source_type"),
        CheckConstraint(
            "price_range IS NULL OR price_range IN "
            "('under_200', '200_to_400', '400_to_800', 'over_800')",
            name="ck_restaurants_price_range",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_restaurants_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_restaurants_longitude"
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_restaurants_coordinate_pair"
        ),
        Index("ix_restaurants_location_gist", "location", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(Text)
    menu_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    primary_cuisine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cuisines.id", ondelete="RESTRICT"), nullable=True
    )
    price_range: Mapped[str | None] = mapped_column(String(24), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source_type: Mapped[str] = mapped_column(String(16), default="manual")
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed(
            "CASE WHEN latitude IS NULL THEN NULL ELSE "
            "ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography END",
            persisted=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    primary_cuisine: Mapped[Cuisine | None] = relationship()
    menus: Mapped[list[RestaurantMenu]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        order_by="RestaurantMenu.created_at",
    )
    photos: Mapped[list[RestaurantPhoto]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        order_by="(RestaurantPhoto.sort_order, RestaurantPhoto.created_at)",
    )


class RestaurantMenu(Base):
    """A manually maintained restaurant menu link / 管理員維護的餐廳菜單連結。"""

    __tablename__ = "restaurant_menus"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(String(1000))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="menus")


class RestaurantPhoto(Base):
    """A manually maintained restaurant photo link / 管理員維護的餐廳照片連結。"""

    __tablename__ = "restaurant_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(1000))
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="photos")


class RestaurantReviewThread(Base):
    """One user's review thread for a restaurant / 一位使用者對一家餐廳的留言串。"""

    __tablename__ = "restaurant_review_threads"
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "user_id",
            name="uq_restaurant_review_threads_restaurant_user",
        ),
        Index(
            "ix_restaurant_review_threads_restaurant_user",
            "restaurant_id",
            "user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    entries: Mapped[list[RestaurantReview]] = relationship(
        back_populates="thread",
        order_by="RestaurantReview.entry_number",
    )


class RestaurantReview(Base):
    """One entry in a review thread / 留言串中的一次原始留言或再訪紀錄。"""

    __tablename__ = "restaurant_reviews"
    __table_args__ = (
        CheckConstraint(
            "revisit_status IN ('will_return', 'neutral', 'will_not_return')",
            name="ck_restaurant_reviews_revisit_status",
        ),
        Index("ix_restaurant_reviews_restaurant_created", "restaurant_id", "created_at"),
        Index(
            "ix_restaurant_reviews_restaurant_user_created",
            "restaurant_id",
            "user_id",
            "created_at",
        ),
        UniqueConstraint(
            "thread_id",
            "entry_number",
            name="uq_restaurant_reviews_thread_entry_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurant_review_threads.id", ondelete="CASCADE"),
        index=True,
    )
    entry_number: Mapped[int] = mapped_column(Integer)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    revisit_status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    restaurant: Mapped[Restaurant] = relationship()
    user: Mapped[User] = relationship()
    thread: Mapped[RestaurantReviewThread] = relationship(back_populates="entries")
    reasons: Mapped[list[ReviewReason]] = relationship(
        secondary="restaurant_review_reasons",
        order_by="ReviewReason.display_name",
    )


class ReviewReason(Base):
    """Reusable review reason / 可重用的留言原因標籤。"""

    __tablename__ = "review_reasons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    polarity: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


restaurant_review_reasons = Table(
    "restaurant_review_reasons",
    Base.metadata,
    Column(
        "review_id",
        UUID(as_uuid=True),
        ForeignKey("restaurant_reviews.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "reason_id",
        UUID(as_uuid=True),
        ForeignKey("review_reasons.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class ReviewLike(Base):
    """One user's like on a review / 使用者對留言的一次按讚關係。"""

    __tablename__ = "review_likes"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurant_reviews.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Friendship(Base):
    """Canonical bidirectional friendship / 以排序使用者配對保存雙向好友關係。"""

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="ck_friendships_canonical_pair"),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FriendRequest(Base):
    """One directed friend request / 一筆有方向的好友邀請。"""

    __tablename__ = "friend_requests"
    __table_args__ = (
        CheckConstraint("requester_id <> recipient_id", name="ck_friend_requests_distinct_users"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_friend_requests_status",
        ),
        Index("ix_friend_requests_recipient_status", "recipient_id", "status"),
        Index(
            "uq_friend_requests_pending_direction",
            "requester_id",
            "recipient_id",
            unique=True,
            postgresql_where="status = 'pending'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Block(Base):
    """Directed block relation / 有方向的封鎖關係。"""

    __tablename__ = "blocks"
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="ck_blocks_distinct_users"),)

    blocker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserFollow(Base):
    """One-way follow relation / 單向追蹤關係。"""

    __tablename__ = "user_follows"
    __table_args__ = (
        CheckConstraint("follower_id <> followed_id", name="ck_user_follows_distinct_users"),
    )

    follower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RestaurantFavorite(Base):
    """One user's restaurant favorite / 使用者與餐廳的一筆收藏關係。"""

    __tablename__ = "restaurant_favorites"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MealEvent(Base):
    """A hosted meal with an open or approval-based join policy / 一場可加入或需審核的約飯。"""

    __tablename__ = "meal_events"
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'private')", name="ck_meal_events_visibility"),
        CheckConstraint(
            "status IN ('open', 'awaiting_host_decision', 'voting', 'decided', "
            "'cancelled', 'completed')",
            name="ck_meal_events_status",
        ),
        CheckConstraint("capacity >= 2", name="ck_meal_events_capacity"),
        Index("ix_meal_events_visibility_status_time", "visibility", "status", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    visibility: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    join_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="open")
    decided_restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    host: Mapped[User] = relationship(foreign_keys=[host_user_id])
    decided_restaurant: Mapped[Restaurant | None] = relationship(
        foreign_keys=[decided_restaurant_id]
    )
    memberships: Mapped[list[MealMembership]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )
    candidates: Mapped[list[MealCandidate]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", order_by="MealCandidate.position"
    )
    votes: Mapped[list[MealVote]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealMembership(Base):
    """One user's current membership state in a meal / 一位使用者在約飯中的成員狀態。"""

    __tablename__ = "meal_memberships"
    __table_args__ = (
        CheckConstraint(
            "membership_status IN ('host', 'member', 'pending', 'rejected', 'left', 'removed')",
            name="ck_meal_memberships_status",
        ),
        Index("ix_meal_memberships_meal_status", "meal_event_id", "membership_status"),
    )

    meal_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    membership_status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meal: Mapped[MealEvent] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class MealCandidate(Base):
    """A restaurant eligible for a meal's one-person-one-vote ballot / 約飯投票候選餐廳。"""

    __tablename__ = "meal_candidates"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 3", name="ck_meal_candidates_position"),
        UniqueConstraint("meal_event_id", "restaurant_id", name="uq_meal_candidates_restaurant"),
        UniqueConstraint("meal_event_id", "position", name="uq_meal_candidates_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="CASCADE"), index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="RESTRICT")
    )
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meal: Mapped[MealEvent] = relationship(back_populates="candidates")
    restaurant: Mapped[Restaurant] = relationship()


class MealVote(Base):
    """The latest ballot cast by one formal member / 一位正式成員投出的最新選票。"""

    __tablename__ = "meal_votes"

    meal_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="CASCADE"), primary_key=True
    )
    voter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meal_candidates.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meal: Mapped[MealEvent] = relationship(back_populates="votes")
    voter: Mapped[User] = relationship(foreign_keys=[voter_user_id])
    candidate: Mapped[MealCandidate] = relationship()


class Conversation(Base):
    """A persistent direct or meal conversation / 永久保存的私訊或飯局聊天室。"""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("kind IN ('meal', 'direct')", name="ck_conversations_kind"),
        CheckConstraint(
            "(kind = 'meal' AND meal_event_id IS NOT NULL) OR "
            "(kind = 'direct' AND meal_event_id IS NULL)",
            name="ck_conversations_kind_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meal_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meal: Mapped[MealEvent | None] = relationship()
    members: Mapped[list[ConversationMember]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMember(Base):
    """Historical participation in a conversation / 聊天室參與歷程。"""

    __tablename__ = "conversation_members"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class DirectConversationPair(Base):
    """Unique identity for one direct conversation / 一對一私訊聊天室的唯一配對。"""

    __tablename__ = "direct_conversation_pairs"
    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="ck_direct_pairs_canonical_pair"),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    """One persisted plain-text chat message / 一筆永久保存的純文字訊息。"""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 2000", name="ck_messages_content_length"
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship()
    reply_to: Mapped[Message | None] = relationship(
        remote_side="Message.id", foreign_keys=[reply_to_message_id]
    )
    pin: Mapped[MessagePin | None] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


class MessagePin(Base):
    """Conversation-level pin for a message / 聊天室層級的訊息釘選。"""

    __tablename__ = "message_pins"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    pinned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message: Mapped[Message] = relationship(back_populates="pin")
    pinned_by: Mapped[User] = relationship()


class AuditLog(Base):
    """Immutable administrator action history / 不可變的管理操作紀錄。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    changes: Mapped[list[AuditLogChange]] = relationship(
        back_populates="audit_log",
        cascade="all, delete-orphan",
    )


class AuditLogChange(Base):
    """One changed field in an audit event / 單次稽核事件中的一個欄位變更。"""

    __tablename__ = "audit_log_changes"

    audit_log_id: Mapped[int] = mapped_column(
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    field_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    audit_log: Mapped[AuditLog] = relationship(back_populates="changes")
