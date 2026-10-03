"""Map query cache and monitoring unit tests / 地圖快取與監控單元測試。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from api.domain.schemas import MapRestaurantsResponse
from api.services.map_observability import (
    MapPerformanceMonitor,
    MapQueryCache,
    MapQueryCacheKey,
    MapQueryEvent,
)


def _key() -> MapQueryCacheKey:
    return MapQueryCacheKey(
        west=121.1,
        south=24.8,
        east=121.3,
        north=25.1,
        zoom=13,
        city=None,
        district=None,
        cuisine_ids=(),
        price_ranges=(),
        result_limit=250,
    )


def test_map_query_cache_returns_stored_response_and_can_clear() -> None:
    cache = MapQueryCache()
    response = MapRestaurantsResponse(status="ok", restaurants=[])

    assert cache.get(_key()) is None
    cache.set(_key(), response)
    assert cache.get(_key()) == response
    assert cache.size == 1

    cache.clear()
    assert cache.get(_key()) is None
    assert cache.size == 0


def test_map_monitoring_calculates_rolling_metrics_and_upgrade_alerts() -> None:
    monitor = MapPerformanceMonitor()
    for _ in range(10):
        monitor.record(
            duration_ms=900,
            result_count=250,
            cache_hit=False,
            response_status="zoom_required",
            query_summary="zoom=12; bounds=121.100,24.800,121.300,25.100; filters=none",
        )
    monitor.record(
        duration_ms=100,
        result_count=2,
        cache_hit=True,
        response_status="ok",
        query_summary="zoom=15; bounds=121.100,24.800,121.300,25.100; filters=none",
    )

    snapshot = monitor.snapshot(published_restaurant_count=10, cache_entries=1)

    assert snapshot["query_count"] == 11
    assert snapshot["cache_hit_rate"] == pytest.approx(1 / 11, abs=0.0001)
    assert snapshot["zoom_required_rate"] == pytest.approx(10 / 11, abs=0.0001)
    assert snapshot["status"] == "normal"
    assert snapshot["alerts"] == []
    assert len(snapshot["recent_queries"]) == 11


def test_map_monitoring_requires_three_windows_before_alerting() -> None:
    monitor = MapPerformanceMonitor()
    now = datetime.now(UTC)
    bucket_seconds = 300
    current_bucket = int(now.timestamp()) // bucket_seconds

    for offset in range(3):
        bucket_start = (current_bucket - offset) * bucket_seconds
        for index in range(10):
            monitor._events.append(  # noqa: SLF001 - seed fixed five-minute windows
                MapQueryEvent(
                    occurred_at=datetime.fromtimestamp(bucket_start + 20 + index, UTC),
                    duration_ms=900,
                    result_count=250,
                    cache_hit=False,
                    response_status="zoom_required",
                    query_summary="test",
                )
            )

    snapshot = monitor.snapshot(published_restaurant_count=10, cache_entries=1)

    assert snapshot["status"] == "attention"
    assert any("後端群聚" in alert for alert in snapshot["alerts"])
