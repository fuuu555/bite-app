import os
import uuid
from datetime import UTC

import pytest
from sqlalchemy import delete, func, select

from api.core.database import session_factory
from api.domain.models import TourismDeletedSourceRecord, TourismImportRun, TourismSourcePlace
from api.domain.schemas import TourismPlacesDeleteRequest
from api.services.tourism_data import (
    delete_tourism_place,
    delete_tourism_places,
    import_dataset_document,
    list_tourism_duplicate_pairs,
    normalize_dataset_document,
    normalize_tourism_name,
)


def test_tourism_batch_delete_request_requires_unique_bounded_ids() -> None:
    place_id = uuid.uuid4()
    with pytest.raises(ValueError):
        TourismPlacesDeleteRequest(place_ids=[place_id, place_id])
    with pytest.raises(ValueError):
        TourismPlacesDeleteRequest(place_ids=[])
    with pytest.raises(ValueError):
        TourismPlacesDeleteRequest(place_ids=[uuid.uuid4() for _ in range(101)])


def test_normalize_tourism_name_ignores_spacing_punctuation_and_width() -> None:
    assert normalize_tourism_name("中原大學 測試店（中壢店）") == "中原大學測試店中壢店"
    assert normalize_tourism_name("ＢｉｔｅＭａｐ，店家") == "bitemap店家"


def test_normalize_food_document_builds_shared_place_shape() -> None:
    places, invalid_count, seen_ids = normalize_dataset_document(
        "food",
        {
            "Restaurants": [
                {
                    "RestaurantID": "Restaurant_demo_1",
                    "RestaurantName": "  測試餐廳  ",
                    "Description": "測試描述",
                    "PositionLat": 25.0478,
                    "PositionLon": 121.5319,
                    "PostalAddress": {
                        "City": "臺北市",
                        "Town": "中正區",
                        "StreetAddress": "測試路 1 號",
                    },
                    "Telephones": [{"Tel": "02-12345678"}],
                    "WebsiteURL": "https://example.com",
                    "ServiceTimeInfo": "每日 11:00-20:00",
                    "UpdateTime": "2026-10-03T02:30:29+08:00",
                },
                {
                    "RestaurantID": "Restaurant_invalid",
                    "RestaurantName": "沒有座標",
                    "PositionLat": None,
                    "PositionLon": None,
                },
            ]
        },
    )

    assert invalid_count == 1
    assert seen_ids == {"Restaurant_demo_1", "Restaurant_invalid"}
    assert len(places) == 1
    place = places[0]
    assert place.category == "restaurant"
    assert place.name == "測試餐廳"
    assert place.address == "臺北市中正區測試路 1 號"
    assert place.phone == "02-12345678"
    assert place.source_updated_at is not None
    assert place.source_updated_at.astimezone(UTC).hour == 18


def test_normalize_attraction_document_rejects_out_of_range_coordinates() -> None:
    places, invalid_count, seen_ids = normalize_dataset_document(
        "attraction",
        {
            "Attractions": [
                {
                    "AttractionID": "Attraction_demo_1",
                    "AttractionName": "測試景點",
                    "PositionLat": 91,
                    "PositionLon": 121,
                }
            ]
        },
    )

    assert places == []
    assert invalid_count == 1
    assert seen_ids == {"Attraction_demo_1"}


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)
async def test_duplicate_region_filter_matches_either_record_address() -> None:
    token = uuid.uuid4().hex[:12]
    name = f"重複比對測試{token}餐廳"
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    base_values = {
        "source_dataset": "food",
        "category": "restaurant",
        "name": name,
        "latitude": 24.95,
        "longitude": 121.22,
        "content_hash": "a" * 64,
        "raw_payload": {},
    }
    async with session_factory() as session:
        session.add_all(
            [
                TourismSourcePlace(
                    id=left_id,
                    source_record_id=f"left-{token}",
                    address="桃園市中壢區測試路 1 號",
                    **base_values,
                ),
                TourismSourcePlace(
                    id=right_id,
                    source_record_id=f"right-{token}",
                    address="測試路 1 號",
                    **base_values,
                ),
            ]
        )
        await session.commit()
        try:
            filtered = await list_tourism_duplicate_pairs(
                session,
                offset=0,
                limit=10,
                query=token,
                city="桃園市",
                district="中壢區",
            )
            excluded = await list_tourism_duplicate_pairs(
                session,
                offset=0,
                limit=10,
                query=token,
                city="臺北市",
            )
            assert filtered.total == 1
            assert excluded.total == 0
        finally:
            await session.execute(
                delete(TourismSourcePlace).where(
                    TourismSourcePlace.id.in_((left_id, right_id))
                )
            )
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)
async def test_deleted_tourism_record_stays_deleted_after_reimport() -> None:
    token = uuid.uuid4().hex
    source_record_id = f"deleted-{token}"
    place_id = uuid.uuid4()
    run_id: uuid.UUID | None = None
    async with session_factory() as session:
        session.add(
            TourismSourcePlace(
                id=place_id,
                source_dataset="food",
                source_record_id=source_record_id,
                category="restaurant",
                name="即將刪除的測試餐廳",
                address="桃園市中壢區測試路 2 號",
                latitude=24.95,
                longitude=121.22,
                content_hash="b" * 64,
                raw_payload={},
            )
        )
        await session.commit()

        try:
            await delete_tourism_place(session, place_id)
            run = TourismImportRun(source_dataset="food", source_url="https://example.test")
            session.add(run)
            await session.flush()
            run_id = run.id
            await import_dataset_document(
                session,
                "food",
                {
                    "Restaurants": [
                        {
                            "RestaurantID": source_record_id,
                            "RestaurantName": "即將刪除的測試餐廳",
                            "PositionLat": 24.95,
                            "PositionLon": 121.22,
                        }
                    ]
                },
                import_run=run,
                deactivate_missing=False,
            )
            await session.commit()
            place = await session.scalar(
                select(TourismSourcePlace).where(
                    TourismSourcePlace.source_dataset == "food",
                    TourismSourcePlace.source_record_id == source_record_id,
                )
            )
            tombstone = await session.scalar(
                select(TourismDeletedSourceRecord).where(
                    TourismDeletedSourceRecord.source_dataset == "food",
                    TourismDeletedSourceRecord.source_record_id == source_record_id,
                )
            )
            assert place is None
            assert tombstone is not None
        finally:
            await session.execute(
                delete(TourismSourcePlace).where(TourismSourcePlace.id == place_id)
            )
            await session.execute(
                delete(TourismDeletedSourceRecord).where(
                    TourismDeletedSourceRecord.source_dataset == "food",
                    TourismDeletedSourceRecord.source_record_id == source_record_id,
                )
            )
            if run_id is not None:
                await session.execute(delete(TourismImportRun).where(TourismImportRun.id == run_id))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)
async def test_batch_tourism_delete_is_atomic_and_records_tombstones() -> None:
    token = uuid.uuid4().hex
    food_id = uuid.uuid4()
    attraction_id = uuid.uuid4()
    source_records = [
        ("food", f"batch-food-{token}"),
        ("attraction", f"batch-attraction-{token}"),
    ]
    async with session_factory() as session:
        for place_id, (dataset, source_record_id) in zip(
            (food_id, attraction_id), source_records, strict=True
        ):
            session.add(
                TourismSourcePlace(
                    id=place_id,
                    source_dataset=dataset,
                    source_record_id=source_record_id,
                    category="restaurant" if dataset == "food" else "attraction",
                    name=f"批次刪除測試 {token}",
                    address="桃園市中壢區測試路 1 號",
                    latitude=24.95,
                    longitude=121.22,
                    content_hash="c" * 64,
                    raw_payload={},
                )
            )
        await session.commit()

        try:
            with pytest.raises(ValueError, match="not found"):
                await delete_tourism_places(session, [food_id, uuid.uuid4()])
            remaining = await session.scalar(
                select(func.count()).select_from(TourismSourcePlace).where(
                    TourismSourcePlace.id.in_((food_id, attraction_id))
                )
            )
            assert remaining == 2

            deleted_ids = await delete_tourism_places(session, [food_id, attraction_id])
            assert set(deleted_ids) == {food_id, attraction_id}
            remaining = await session.scalar(
                select(func.count()).select_from(TourismSourcePlace).where(
                    TourismSourcePlace.id.in_((food_id, attraction_id))
                )
            )
            tombstones = list(
                (
                    await session.scalars(
                        select(TourismDeletedSourceRecord).where(
                            TourismDeletedSourceRecord.source_record_id.in_(
                                [source_id for _, source_id in source_records]
                            )
                        )
                    )
                ).all()
            )
            assert remaining == 0
            assert len(tombstones) == 2
        finally:
            await session.execute(
                delete(TourismSourcePlace).where(
                    TourismSourcePlace.id.in_((food_id, attraction_id))
                )
            )
            await session.execute(
                delete(TourismDeletedSourceRecord).where(
                    TourismDeletedSourceRecord.source_record_id.in_(
                        [source_id for _, source_id in source_records]
                    )
                )
            )
            await session.commit()
