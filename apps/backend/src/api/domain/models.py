"""Application persistence models / 應用程式資料庫模型。"""

from __future__ import annotations

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


class UserProfile(Base):
    """User-owned public profile fields / 使用者可管理的公開個人資料。"""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="profile")
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
