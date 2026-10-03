"""Tourism open-data import and read services / 觀光開放資料匯入與讀取服務。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, cast

import httpx
from geoalchemy2 import Geography
from sqlalchemy import Select, and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.core.database import session_factory
from api.domain.models import (
    Cuisine,
    TourismDeletedSourceRecord,
    TourismImportRun,
    TourismSourcePlace,
)
from api.domain.schemas import (
    TourismAdminPlaceResponse,
    TourismDuplicatePairResponse,
    TourismDuplicatePairsResponse,
    TourismPlaceCategory,
    TourismPlaceResponse,
    TourismPlaceUpdate,
    TourismSourceDataset,
)


@dataclass(frozen=True)
class TourismDatasetConfig:
    dataset: TourismSourceDataset
    category: TourismPlaceCategory
    source_url: str
    archive_member: str
    collection_key: str
    source_id_key: str
    name_key: str


DATASET_CONFIGS: dict[TourismSourceDataset, TourismDatasetConfig] = {
    "food": TourismDatasetConfig(
        dataset="food",
        category="restaurant",
        source_url="https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Restaurant-json.zip",
        archive_member="RestaurantList.json",
        collection_key="Restaurants",
        source_id_key="RestaurantID",
        name_key="RestaurantName",
    ),
    "attraction": TourismDatasetConfig(
        dataset="attraction",
        category="attraction",
        source_url="https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Attraction-json.zip",
        archive_member="AttractionList.json",
        collection_key="Attractions",
        source_id_key="AttractionID",
        name_key="AttractionName",
    ),
    "hotel": TourismDatasetConfig(
        dataset="hotel",
        category="hotel",
        source_url="https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/Hotel-json.zip",
        archive_member="HotelList.json",
        collection_key="Hotels",
        source_id_key="HotelID",
        name_key="HotelName",
    ),
    "service_site": TourismDatasetConfig(
        dataset="service_site",
        category="service_site",
        source_url=(
            "https://media.taiwan.net.tw/XMLReleaseAll_public/v2.0/Zh_tw/"
            "TourismServiceSite-json.zip"
        ),
        archive_member="TourismServiceSiteList.json",
        collection_key="TourismServiceSites",
        source_id_key="TourismServiceSiteID",
        name_key="TourismServiceSiteName",
    ),
}
_import_lock = asyncio.Lock()
TOURISM_CLASSIFICATION_BY_DATASET: dict[TourismSourceDataset, str] = {
    "food": "tourism-food",
    "attraction": "tourism-attraction",
    "hotel": "tourism-lodging",
    "service_site": "tourism-service-site",
}
SYSTEM_TOURISM_CLASSIFICATION_SLUGS = frozenset(TOURISM_CLASSIFICATION_BY_DATASET.values())
TOURISM_CLASSIFICATION_NAME_BY_DATASET: dict[TourismSourceDataset, str] = {
    "food": "餐飲",
    "attraction": "景點",
    "hotel": "旅館民宿",
    "service_site": "旅遊服務站",
}
TOURISM_CLASSIFICATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("tourism-food", "餐飲", "tools-kitchen-3", "#F26B4F"),
    ("tourism-attraction", "景點", "map-pin", "#657B8C"),
    ("tourism-lodging", "旅館民宿", "bed", "#8B6BB1"),
    ("tourism-service-site", "旅遊服務站", "info-circle", "#4E8F6B"),
)


@dataclass(frozen=True)
class NormalizedTourismPlace:
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
    content_hash: str
    tags: list[str]
    icon_key: str
    icon_color: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class TourismImportReport:
    source_dataset: TourismSourceDataset
    downloaded_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    invalid_count: int
    deactivated_count: int


def dataset_config(dataset: TourismSourceDataset) -> TourismDatasetConfig:
    """Return configuration for a supported source dataset / 取得資料集設定。"""
    try:
        return DATASET_CONFIGS[dataset]
    except KeyError as error:
        raise ValueError(f"unsupported tourism dataset: {dataset}") from error


async def download_dataset_document(
    dataset: TourismSourceDataset,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Download and decode one official JSON ZIP archive."""
    config = dataset_config(dataset)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=15.0),
        follow_redirects=True,
        headers={"User-Agent": "BiteMap tourism open-data importer/0.1"},
    )
    try:
        response = await http_client.get(config.source_url)
        response.raise_for_status()
    finally:
        if owns_client:
            await http_client.aclose()

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        member = next(
            (name for name in archive.namelist() if name.endswith(config.archive_member)),
            None,
        )
        if member is None:
            raise ValueError(f"{config.archive_member} not found in tourism archive")
        document = json.loads(archive.read(member).decode("utf-8-sig"))

    if not isinstance(document, dict):
        raise ValueError("tourism source document must be a JSON object")
    return cast(dict[str, Any], document)


def normalize_dataset_document(
    dataset: TourismSourceDataset,
    document: dict[str, Any],
) -> tuple[list[NormalizedTourismPlace], int, set[str]]:
    """Normalize official records and return valid rows, invalid count, and seen IDs."""
    config = dataset_config(dataset)
    raw_records = document.get(config.collection_key)
    if not isinstance(raw_records, list):
        raise ValueError(f"missing collection {config.collection_key}")

    normalized: list[NormalizedTourismPlace] = []
    invalid_count = 0
    seen_ids: set[str] = set()
    for raw_record in raw_records:
        if not isinstance(raw_record, dict):
            invalid_count += 1
            continue
        raw = cast(dict[str, Any], raw_record)
        source_record_id = _text(raw.get(config.source_id_key))
        if source_record_id:
            seen_ids.add(source_record_id)

        name = _text(raw.get(config.name_key))
        latitude = _float(raw.get("PositionLat"))
        longitude = _float(raw.get("PositionLon"))
        if not source_record_id or not name or latitude is None or longitude is None:
            invalid_count += 1
            continue
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            invalid_count += 1
            continue

        normalized.append(
            NormalizedTourismPlace(
                source_dataset=dataset,
                source_record_id=source_record_id,
                category=config.category,
                name=name,
                description=_text(raw.get("Description")),
                address=_address(raw.get("PostalAddress")),
                phone=_phones(raw.get("Telephones")),
                latitude=latitude,
                longitude=longitude,
                official_url=_text(raw.get("WebsiteURL")),
                opening_hours=_text(raw.get("ServiceTimeInfo")),
                source_updated_at=_datetime(raw.get("UpdateTime")),
                content_hash=_content_hash(raw),
                tags=_classify_tags(dataset, name, raw),
                icon_key=_icon_key(dataset, name, raw),
                icon_color=_icon_color(dataset),
                raw_payload=raw,
            )
        )

    return normalized, invalid_count, seen_ids


async def import_dataset_document(
    session: AsyncSession,
    dataset: TourismSourceDataset,
    document: dict[str, Any],
    *,
    fetched_at: datetime | None = None,
    import_run: TourismImportRun | None = None,
    deactivate_missing: bool = True,
) -> TourismImportReport:
    """Idempotently upsert one source document and deactivate removed records."""
    config = dataset_config(dataset)
    fetched_at = fetched_at or datetime.now(UTC)
    normalized, invalid_count, seen_ids = normalize_dataset_document(dataset, document)
    raw_records = document.get(config.collection_key)
    downloaded_count = len(raw_records) if isinstance(raw_records, list) else 0

    run = import_run
    if run is None:
        run = TourismImportRun(source_dataset=dataset, source_url=config.source_url)
        session.add(run)
        await session.flush()

    await session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"bitemap-tourism-import:{dataset}", 0)
            )
        )
    )
    deleted_record_result = await session.execute(
        select(TourismDeletedSourceRecord.source_record_id).where(
            TourismDeletedSourceRecord.source_dataset == dataset
        )
    )
    deleted_record_ids = set(deleted_record_result.scalars())

    existing_result = await session.execute(
        select(TourismSourcePlace).where(TourismSourcePlace.source_dataset == dataset)
    )
    existing = {item.source_record_id: item for item in existing_result.scalars()}
    inserted_count = 0
    updated_count = 0
    unchanged_count = 0

    for place in normalized:
        if place.source_record_id in deleted_record_ids:
            continue
        current = existing.get(place.source_record_id)
        if current is None:
            session.add(
                TourismSourcePlace(
                    source_dataset=place.source_dataset,
                    source_record_id=place.source_record_id,
                    category=place.category,
                    name=place.name,
                    description=place.description,
                    address=place.address,
                    phone=place.phone,
                    latitude=place.latitude,
                    longitude=place.longitude,
                    official_url=place.official_url,
                    opening_hours=place.opening_hours,
                    source_updated_at=place.source_updated_at,
                    fetched_at=fetched_at,
                    content_hash=place.content_hash,
                    status="active",
                    tags=place.tags,
                    icon_key=place.icon_key,
                    icon_color=place.icon_color,
                    validation_errors=[],
                    raw_payload=place.raw_payload,
                )
            )
            inserted_count += 1
            continue

        if (
            current.content_hash == place.content_hash
            and current.status == "active"
            and current.tags == place.tags
            and current.icon_key == place.icon_key
            and current.icon_color == place.icon_color
            and current.display_icon_key is None
        ):
            current.fetched_at = fetched_at
            unchanged_count += 1
            continue

        for field in (
            "category",
            "name",
            "description",
            "address",
            "phone",
            "latitude",
            "longitude",
            "official_url",
            "opening_hours",
            "source_updated_at",
            "content_hash",
            "tags",
            "icon_key",
            "icon_color",
            "raw_payload",
        ):
            setattr(current, field, getattr(place, field))
        current.fetched_at = fetched_at
        current.status = "active"
        current.validation_errors = []
        # Re-import reapplies source-type classification and drops stale manual icon picks.
        current.display_icon_key = None
        updated_count += 1

    deactivated_count = 0
    if deactivate_missing:
        for record_id, current in existing.items():
            if record_id not in seen_ids and current.status == "active":
                current.status = "inactive"
                current.fetched_at = fetched_at
                deactivated_count += 1

    run.status = "succeeded"
    run.completed_at = datetime.now(UTC)
    run.downloaded_count = downloaded_count
    run.inserted_count = inserted_count
    run.updated_count = updated_count
    run.unchanged_count = unchanged_count
    run.invalid_count = invalid_count
    run.deactivated_count = deactivated_count
    await session.flush()

    return TourismImportReport(
        source_dataset=dataset,
        downloaded_count=downloaded_count,
        inserted_count=inserted_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
        invalid_count=invalid_count,
        deactivated_count=deactivated_count,
    )


def tourism_import_in_progress() -> bool:
    """Return whether the current API process is importing tourism data."""
    return _import_lock.locked()


async def import_all_tourism_datasets() -> None:
    """Import every configured official dataset for the admin background job."""
    if _import_lock.locked():
        return

    async with _import_lock:
        async with session_factory() as session:
            await ensure_tourism_classifications(session)
        for dataset in DATASET_CONFIGS:
            run_id: uuid.UUID | None = None
            try:
                async with session_factory() as session:
                    run = TourismImportRun(
                        source_dataset=dataset,
                        source_url=DATASET_CONFIGS[dataset].source_url,
                    )
                    session.add(run)
                    await session.flush()
                    run_id = run.id
                    await session.commit()

                document = await download_dataset_document(dataset)
                async with session_factory() as session:
                    run = await session.get(TourismImportRun, run_id)
                    if run is None:
                        raise RuntimeError("tourism import run disappeared")
                    await import_dataset_document(session, dataset, document, import_run=run)
                    await session.commit()
            except Exception as error:  # pragma: no cover - exercised by live import failures
                if run_id is None:
                    continue
                async with session_factory() as session:
                    run = await session.get(TourismImportRun, run_id)
                    if run is not None:
                        run.status = "failed"
                        run.completed_at = datetime.now(UTC)
                        run.error_message = str(error)[:2000]
                        await session.commit()


async def ensure_tourism_classifications(session: AsyncSession) -> None:
    """Create missing official-data icon categories before importing places."""
    result = await session.execute(select(Cuisine))
    cuisines = list(result.scalars())
    slugs = {cuisine.slug: cuisine for cuisine in cuisines}
    display_names = {cuisine.display_name.strip(): cuisine for cuisine in cuisines}
    for slug, display_name, icon_key, color in TOURISM_CLASSIFICATIONS:
        cuisine = slugs.get(slug) or display_names.get(display_name)
        if cuisine is None:
            session.add(
                Cuisine(
                    slug=slug,
                    display_name=display_name,
                    icon_key=icon_key,
                    color=color,
                    is_active=True,
                )
            )
            continue
        cuisine.slug = slug
        cuisine.display_name = display_name
        cuisine.icon_key = icon_key
        cuisine.color = color
        cuisine.is_active = True
    await session.commit()


async def query_tourism_places(
    session: AsyncSession,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    categories: list[TourismPlaceCategory] | None,
    datasets: list[TourismSourceDataset] | None,
    result_limit: int,
) -> tuple[list[TourismPlaceResponse], bool]:
    """Query active external places inside one bounded viewport."""
    viewport = func.ST_MakeEnvelope(west, south, east, north, 4326).cast(
        Geography(geometry_type="POLYGON", srid=4326)
    )
    statement: Select[tuple[TourismSourcePlace]] = (
        select(TourismSourcePlace)
        .where(
            TourismSourcePlace.status == "active",
            TourismSourcePlace.is_map_enabled.is_(True),
            TourismSourcePlace.location.is_not(None),
            func.ST_Intersects(TourismSourcePlace.location, viewport),
        )
        .order_by(TourismSourcePlace.category, TourismSourcePlace.name, TourismSourcePlace.id)
        .limit(result_limit + 1)
    )
    if categories:
        statement = statement.where(TourismSourcePlace.category.in_(categories))
    if datasets:
        statement = statement.where(TourismSourcePlace.source_dataset.in_(datasets))

    places = list((await session.execute(statement)).scalars())
    active_cuisines = await _active_cuisines(session)
    has_more = len(places) > result_limit
    return [
        _place_response(place, active_cuisines) for place in places[:result_limit]
    ], has_more


async def _active_cuisines(session: AsyncSession) -> dict[str, Cuisine]:
    result = await session.execute(select(Cuisine).where(Cuisine.is_active.is_(True)))
    return {cuisine.slug: cuisine for cuisine in result.scalars()}


def _tourism_classification(
    place: TourismSourcePlace,
    active_cuisines: dict[str, Cuisine],
) -> Cuisine | None:
    classification_slug = place.display_icon_key or TOURISM_CLASSIFICATION_BY_DATASET[
        cast(TourismSourceDataset, place.source_dataset)
    ]
    cuisine = active_cuisines.get(classification_slug)
    if cuisine is not None:
        return cuisine
    expected_name = TOURISM_CLASSIFICATION_NAME_BY_DATASET[
        cast(TourismSourceDataset, place.source_dataset)
    ]
    cuisine = next(
        (
            item
            for item in active_cuisines.values()
            if item.display_name.strip() == expected_name
        ),
        None,
    )
    if cuisine is not None and not place.display_icon_key:
        return cuisine
    # Keep compatibility with rows edited by earlier versions that stored icon_key.
    return next(
        (
            item
            for item in active_cuisines.values()
            if item.icon_key == classification_slug
        ),
        None,
    )


def _place_response(
    place: TourismSourcePlace,
    active_cuisines: dict[str, Cuisine],
) -> TourismPlaceResponse:
    if place.latitude is None or place.longitude is None:
        raise ValueError("active tourism place is missing coordinates")
    cuisine = _tourism_classification(place, active_cuisines)
    return TourismPlaceResponse(
        id=place.id,
        source_dataset=cast(TourismSourceDataset, place.source_dataset),
        source_record_id=place.source_record_id,
        category=cast(TourismPlaceCategory, place.category),
        name=place.display_name or place.name,
        description=place.description,
        address=place.display_address or place.address,
        phone=place.phone,
        latitude=place.latitude,
        longitude=place.longitude,
        official_url=place.official_url,
        opening_hours=place.opening_hours,
        source_updated_at=place.source_updated_at,
        tags=cast(list[str], place.tags),
        icon_key=cuisine.icon_key if cuisine else None,
        icon_classification_slug=cuisine.slug if cuisine else None,
        icon_color=cuisine.color if cuisine else place.icon_color,
    )


async def list_admin_tourism_places(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
    dataset: TourismSourceDataset | None,
    query: str | None,
    city: str | None = None,
    district: str | None = None,
) -> tuple[list[TourismAdminPlaceResponse], int]:
    """List manageable official places grouped by the admin UI's region view."""
    conditions = [
        TourismSourcePlace.status != "invalid",
    ]
    if dataset:
        conditions.append(TourismSourcePlace.source_dataset == dataset)
    if query:
        search = f"%{query.strip()}%"
        conditions.append(
            func.coalesce(TourismSourcePlace.display_name, TourismSourcePlace.name).ilike(search)
            | func.coalesce(
                TourismSourcePlace.display_address, TourismSourcePlace.address
            ).ilike(search)
        )
    if city:
        conditions.append(
            func.coalesce(
                TourismSourcePlace.display_address, TourismSourcePlace.address
            ).ilike(f"%{city.strip()}%")
        )
    if district:
        conditions.append(
            func.coalesce(
                TourismSourcePlace.display_address, TourismSourcePlace.address
            ).ilike(f"%{district.strip()}%")
        )
    total = int(
        await session.scalar(
            select(func.count()).select_from(TourismSourcePlace).where(*conditions)
        )
        or 0
    )
    result = await session.execute(
        select(TourismSourcePlace)
        .where(*conditions)
        .order_by(
            func.coalesce(TourismSourcePlace.display_address, TourismSourcePlace.address),
            func.coalesce(TourismSourcePlace.display_name, TourismSourcePlace.name),
            TourismSourcePlace.id,
        )
        .offset(offset)
        .limit(limit)
    )
    active_cuisines = await _active_cuisines(session)
    return [_admin_place_response(place, active_cuisines) for place in result.scalars()], total


def normalize_tourism_name(value: str | None) -> str:
    """Normalize names for matching punctuation/spacing variants."""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


async def list_tourism_duplicate_pairs(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
    dataset: TourismSourceDataset | None = None,
    query: str | None = None,
    city: str | None = None,
    district: str | None = None,
) -> TourismDuplicatePairsResponse:
    """Return likely duplicate official records for manual review, never auto-merge."""
    left = aliased(TourismSourcePlace, name="left_place")
    right = aliased(TourismSourcePlace, name="right_place")

    def compact(expression):
        return func.lower(
            func.regexp_replace(
                expression,
                r"[[:space:][:punct:]]+",
                "",
                "g",
            )
        )

    left_name = compact(func.coalesce(left.display_name, left.name))
    right_name = compact(func.coalesce(right.display_name, right.name))
    left_address = compact(func.coalesce(left.display_address, left.address, ""))
    right_address = compact(func.coalesce(right.display_address, right.address, ""))
    name_similarity = func.similarity(left_name, right_name)
    address_similarity = func.similarity(left_address, right_address)
    locations_nearby = func.ST_DWithin(left.location, right.location, 300)
    # The trigram operator is index-backed by ix_tourism_source_places_display_name_trgm.
    # Require address or proximity evidence to keep chain branches from flooding the review queue.
    # The trigram name predicate remains indexable through the GIN index above.
    await session.execute(
        select(func.set_config("pg_trgm.similarity_threshold", "0.45", True))
    )
    candidate_match = left_name.op("%")(right_name)
    conditions = [
        left.id < right.id,
        left.status != "invalid",
        right.status != "invalid",
        candidate_match,
        or_(
            and_(left_address != "", right_address != "", address_similarity >= 0.4),
            locations_nearby,
        ),
    ]
    if dataset:
        conditions.append(or_(left.source_dataset == dataset, right.source_dataset == dataset))
    if query and query.strip():
        search = f"%{query.strip()}%"
        conditions.append(
            or_(
                func.coalesce(left.display_name, left.name).ilike(search),
                func.coalesce(right.display_name, right.name).ilike(search),
                func.coalesce(left.display_address, left.address, "").ilike(search),
                func.coalesce(right.display_address, right.address, "").ilike(search),
            )
        )

    if city or district:
        region_filters = []
        for place_alias in (left, right):
            address = func.coalesce(place_alias.display_address, place_alias.address, "")
            member_filters = []
            if city and city.strip():
                member_filters.append(address.ilike(f"%{city.strip()}%"))
            if district and district.strip():
                member_filters.append(address.ilike(f"%{district.strip()}%"))
            if member_filters:
                region_filters.append(and_(*member_filters))
        if region_filters:
            conditions.append(or_(*region_filters))

    total = int(
        await session.scalar(
            select(func.count())
            .select_from(left)
            .join(right, left.id < right.id)
            .where(*conditions)
        )
        or 0
    )
    candidate_score = (
        name_similarity
        + case(
            (and_(left_address != "", right_address != ""), address_similarity * 0.2),
            else_=0.0,
        )
        + case((locations_nearby, 0.15), else_=0.0)
    )
    rows = (
        await session.execute(
            select(left, right, name_similarity, address_similarity, locations_nearby)
            .join(right, left.id < right.id)
            .where(*conditions)
            .order_by(candidate_score.desc(), left.id, right.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    active_cuisines = await _active_cuisines(session)
    pairs: list[TourismDuplicatePairResponse] = []
    for left_place, right_place, name_score, address_score, nearby in rows:
        left_display_name = left_place.display_name or left_place.name
        right_display_name = right_place.display_name or right_place.name
        reasons: list[str] = []
        if normalize_tourism_name(left_display_name) == normalize_tourism_name(right_display_name):
            reasons.append("名稱正規化後相同")
        else:
            reasons.append("名稱相似")
        has_both_addresses = bool(
            (left_place.display_address or left_place.address)
            and (right_place.display_address or right_place.address)
        )
        if has_both_addresses and float(address_score or 0) >= 0.4:
            reasons.append("地址相似")
        if nearby:
            reasons.append("座標相距 300 公尺內")
        pairs.append(
            TourismDuplicatePairResponse(
                left=_admin_place_response(left_place, active_cuisines),
                right=_admin_place_response(right_place, active_cuisines),
                name_similarity=round(float(name_score or 0), 3),
                match_reasons=reasons,
            )
        )
    return TourismDuplicatePairsResponse(
        pairs=pairs,
        total=total,
        has_more=offset + len(pairs) < total,
    )


async def delete_tourism_place(
    session: AsyncSession,
    place_id: uuid.UUID,
) -> None:
    """Delete one official row while suppressing its future imports."""
    await delete_tourism_places(session, [place_id])


async def delete_tourism_places(
    session: AsyncSession,
    place_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """Atomically delete official rows and retain source IDs as import tombstones."""
    unique_ids = list(dict.fromkeys(place_ids))
    if not unique_ids or len(unique_ids) > 100 or len(unique_ids) != len(place_ids):
        raise ValueError("expected 1 to 100 unique tourism place IDs")

    initial_places = list(
        (
            await session.scalars(
                select(TourismSourcePlace).where(TourismSourcePlace.id.in_(unique_ids))
            )
        ).all()
    )
    if len(initial_places) != len(unique_ids):
        await session.rollback()
        raise ValueError("tourism place not found")

    datasets = sorted({place.source_dataset for place in initial_places})
    for dataset in datasets:
        await session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"bitemap-tourism-import:{dataset}", 0)
                )
            )
        )

    places = list(
        (
            await session.scalars(
                select(TourismSourcePlace)
                .where(TourismSourcePlace.id.in_(unique_ids))
                .order_by(TourismSourcePlace.source_dataset, TourismSourcePlace.source_record_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if len(places) != len(unique_ids):
        await session.rollback()
        raise ValueError("tourism place not found")

    tombstones = [
        {
            "source_dataset": place.source_dataset,
            "source_record_id": place.source_record_id,
        }
        for place in places
    ]
    await session.execute(
        pg_insert(TourismDeletedSourceRecord)
        .values(tombstones)
        .on_conflict_do_nothing(
            index_elements=[
                TourismDeletedSourceRecord.source_dataset,
                TourismDeletedSourceRecord.source_record_id,
            ]
        )
    )
    for place in places:
        await session.delete(place)
    await session.commit()
    return [place.id for place in places]


def _admin_place_response(
    place: TourismSourcePlace,
    active_cuisines: dict[str, Cuisine],
) -> TourismAdminPlaceResponse:
    if place.latitude is None or place.longitude is None:
        raise ValueError("tourism place is missing coordinates")
    cuisine = _tourism_classification(place, active_cuisines)
    return TourismAdminPlaceResponse(
        id=place.id,
        source_dataset=cast(TourismSourceDataset, place.source_dataset),
        source_record_id=place.source_record_id,
        category=cast(TourismPlaceCategory, place.category),
        name=place.display_name or place.name,
        description=place.description,
        address=place.display_address or place.address,
        phone=place.phone,
        latitude=place.latitude,
        longitude=place.longitude,
        official_url=place.official_url,
        opening_hours=place.opening_hours,
        source_updated_at=place.source_updated_at,
        tags=cast(list[str], place.tags),
        icon_key=cuisine.icon_key if cuisine else None,
        icon_classification_slug=cuisine.slug if cuisine else None,
        icon_color=cuisine.color if cuisine else place.icon_color,
        official_name=place.name,
        official_address=place.address,
        official_icon_key=place.icon_key,
        is_map_enabled=place.is_map_enabled,
        linked_restaurant_id=place.linked_restaurant_id,
    )


async def get_tourism_place(session: AsyncSession, place_id: uuid.UUID) -> TourismSourcePlace:
    place = await session.get(TourismSourcePlace, place_id)
    if place is None:
        raise ValueError("tourism place not found")
    return place


async def update_tourism_place(
    session: AsyncSession,
    place: TourismSourcePlace,
    payload: TourismPlaceUpdate,
) -> TourismAdminPlaceResponse:
    values = payload.model_dump(exclude_unset=True)
    if "name" in values:
        place.display_name = values["name"]
    if "address" in values:
        place.display_address = values["address"]
    place.display_icon_key = None
    await session.commit()
    await session.refresh(place)
    return _admin_place_response(place, await _active_cuisines(session))


async def enable_all_tourism_places(
    session: AsyncSession,
    *,
    dataset: TourismSourceDataset | None,
) -> int:
    conditions = [
        TourismSourcePlace.status != "invalid",
    ]
    if dataset:
        conditions.append(TourismSourcePlace.source_dataset == dataset)
    result = await session.execute(
        update(TourismSourcePlace).where(*conditions).values(is_map_enabled=True)
    )
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float, str)):
            return float(value)
        return None
    except (TypeError, ValueError):
        return None


def _address(value: object) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if not isinstance(value, dict):
        return None
    parts = [
        _text(value.get("City")),
        _text(value.get("Town")),
        _text(value.get("StreetAddress")),
    ]
    return "".join(part for part in parts if part) or None


def _phones(value: object) -> str | None:
    if not isinstance(value, list):
        return _text(value)
    phones = []
    for item in value:
        if isinstance(item, dict):
            phone = _text(item.get("Tel"))
        else:
            phone = _text(item)
        if phone:
            phones.append(phone)
    return "、".join(dict.fromkeys(phones)) or None


def _datetime(value: object) -> datetime | None:
    text_value = _text(value)
    if not text_value:
        return None
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _content_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _classify_tags(dataset: TourismSourceDataset, name: str, payload: dict[str, Any]) -> list[str]:
    """Assign transparent rule-based tags from official fields."""
    searchable = " ".join(
        value
        for value in (
            name,
            _text(payload.get("Description")),
            _text(payload.get("Remarks")),
            _text(payload.get("AssetsClass")),
            _text(payload.get("HotelClasses")),
        )
        if value
    )
    tags: list[str] = []
    if dataset == "food":
        tags.append("food")
        if any(keyword in searchable for keyword in ("夜市", "市集")):
            tags.append("night_market")
    elif dataset == "hotel":
        tags.append("lodging")
        if "民宿" in searchable:
            tags.append("homestay")
    elif dataset == "service_site":
        tags.append("tourism_service")
    else:
        tags.append("attraction")
        keyword_tags = (
            ("park", ("公園", "森林", "綠地")),
            ("shopping_district", ("商圈", "老街", "商店街")),
            ("play", ("遊樂", "遊憩", "親子", "樂園")),
            ("culture", ("博物館", "美術館", "文化館", "古蹟")),
            ("nature", ("湖", "瀑布", "步道", "自然", "海灘")),
        )
        tags.extend(
            tag
            for tag, keywords in keyword_tags
            if any(keyword in searchable for keyword in keywords)
        )
    return list(dict.fromkeys(tags))


def _icon_key(dataset: TourismSourceDataset, name: str, payload: dict[str, Any]) -> str:
    tags = _classify_tags(dataset, name, payload)
    tag_icons = {
        "food": "tools-kitchen-3",
        "night_market": "building-store",
        "lodging": "bed",
        "homestay": "home",
        "tourism_service": "info-circle",
        "park": "trees",
        "shopping_district": "building-store",
        "play": "confetti",
        "culture": "building-bank",
        "nature": "mountain",
        "attraction": "map-pin",
    }
    return next((tag_icons[tag] for tag in tags if tag in tag_icons), "map-pin")


def _icon_color(dataset: TourismSourceDataset) -> str:
    return {
        "food": "#d96c4f",
        "attraction": "#657b8c",
        "hotel": "#8b6bb1",
        "service_site": "#4e8f6b",
    }[dataset]
