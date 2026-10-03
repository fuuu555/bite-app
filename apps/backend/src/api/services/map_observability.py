"""Map query cache and rolling performance monitoring / 地圖查詢快取與效能監控。"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from time import monotonic
from typing import Any

from api.domain.schemas import MapRestaurantsResponse

WINDOW = timedelta(minutes=5)
CACHE_TTL_SECONDS = 15.0
MAX_EVENTS = 5000
RECENT_QUERY_LIMIT = 20
MIN_WINDOW_QUERIES = 10


@dataclass(frozen=True)
class MapQueryCacheKey:
    """Normalized map query inputs used as an in-process cache key."""

    west: float
    south: float
    east: float
    north: float
    zoom: float
    city: str | None
    district: str | None
    cuisine_ids: tuple[str, ...]
    price_ranges: tuple[str, ...]
    result_limit: int


@dataclass
class _CacheEntry:
    expires_at: float
    response: MapRestaurantsResponse


class MapQueryCache:
    """Small single-process TTL cache; shared cache is a later upgrade path."""

    def __init__(self) -> None:
        self._entries: dict[MapQueryCacheKey, _CacheEntry] = {}

    def get(self, key: MapQueryCacheKey) -> MapRestaurantsResponse | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= monotonic():
            self._entries.pop(key, None)
            return None
        return entry.response

    def set(self, key: MapQueryCacheKey, response: MapRestaurantsResponse) -> None:
        self._entries[key] = _CacheEntry(
            expires_at=monotonic() + CACHE_TTL_SECONDS,
            response=response,
        )

    def clear(self) -> None:
        self._entries.clear()

    @property
    def size(self) -> int:
        self._remove_expired()
        return len(self._entries)

    def _remove_expired(self) -> None:
        now = monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


@dataclass(frozen=True)
class MapQueryEvent:
    occurred_at: datetime
    duration_ms: float
    result_count: int
    cache_hit: bool
    response_status: str
    query_summary: str


class MapPerformanceMonitor:
    """Rolling in-memory measurements for the admin monitoring page."""

    def __init__(self) -> None:
        self._events: deque[MapQueryEvent] = deque(maxlen=MAX_EVENTS)

    def record(
        self,
        *,
        duration_ms: float,
        result_count: int,
        cache_hit: bool,
        response_status: str,
        query_summary: str,
    ) -> None:
        self._events.append(
            MapQueryEvent(
                occurred_at=datetime.now(UTC),
                duration_ms=round(duration_ms, 2),
                result_count=result_count,
                cache_hit=cache_hit,
                response_status=response_status,
                query_summary=query_summary,
            )
        )

    def snapshot(self, *, published_restaurant_count: int, cache_entries: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        cutoff = now - WINDOW
        events = [event for event in self._events if event.occurred_at >= cutoff]
        durations = sorted(event.duration_ms for event in events)
        query_count = len(events)
        cache_hits = sum(event.cache_hit for event in events)
        zoom_required_count = sum(event.response_status == "zoom_required" for event in events)
        error_count = sum(event.response_status == "error" for event in events)
        average_duration = sum(durations) / query_count if query_count else 0.0
        p95_duration = durations[max(0, ceil(query_count * 0.95) - 1)] if durations else 0.0
        cache_hit_rate = cache_hits / query_count if query_count else 0.0
        zoom_required_rate = zoom_required_count / query_count if query_count else 0.0
        error_rate = error_count / query_count if query_count else 0.0

        alerts: list[str] = []
        critical_sustained = self._sustained_for_three_windows(
            lambda window_events: _window_rate(window_events, "error") > 0.02
            or _window_p95(window_events) > 2000,
            now,
        )
        attention_sustained = self._sustained_for_three_windows(
            lambda window_events: _window_p95(window_events) > 800
            or _window_cache_hit_rate(window_events) < 0.4,
            now,
        )
        backend_clustering_sustained = self._sustained_for_three_windows(
            lambda window_events: _window_rate(window_events, "zoom_required") > 0.05,
            now,
        )
        if critical_sustained:
            alerts.append(
                "嚴重：錯誤率超過 2% 或 P95 查詢時間超過 2 秒，請優先檢查資料庫與查詢計畫。"
            )
        elif attention_sustained:
            alerts.append("注意：P95 查詢時間偏高或快取命中率偏低，建議檢查索引與 bounds bucket。")
        if backend_clustering_sustained:
            alerts.append("建議後端群聚：超過 5% 的查詢需要放大地圖。")
        if published_restaurant_count > 5000:
            alerts.append("建議評估向量圖磚：已發布店家超過 5,000 筆。")

        if critical_sustained:
            status = "critical"
        elif alerts:
            status = "attention"
        else:
            status = "normal"

        return {
            "window_minutes": 5,
            "query_count": query_count,
            "average_duration_ms": round(average_duration, 2),
            "p95_duration_ms": round(p95_duration, 2),
            "cache_hits": cache_hits,
            "cache_misses": query_count - cache_hits,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "zoom_required_count": zoom_required_count,
            "zoom_required_rate": round(zoom_required_rate, 4),
            "error_count": error_count,
            "error_rate": round(error_rate, 4),
            "published_restaurant_count": published_restaurant_count,
            "cache_entries": cache_entries,
            "status": status,
            "alerts": alerts,
            "last_updated_at": now,
            "recent_queries": [
                {
                    "occurred_at": event.occurred_at,
                    "duration_ms": event.duration_ms,
                    "result_count": event.result_count,
                    "cache_hit": event.cache_hit,
                    "response_status": event.response_status,
                    "query_summary": event.query_summary,
                }
                for event in reversed(events[-RECENT_QUERY_LIMIT:])
            ],
        }

    def _sustained_for_three_windows(self, predicate: Any, now: datetime) -> bool:
        """Require a threshold to hold in three consecutive five-minute buckets."""
        bucket_seconds = int(WINDOW.total_seconds())
        current_bucket = int(now.timestamp()) // bucket_seconds
        by_bucket: dict[int, list[MapQueryEvent]] = defaultdict(list)
        cutoff = now - (WINDOW * 3)
        for event in self._events:
            if event.occurred_at >= cutoff:
                bucket = int(event.occurred_at.timestamp()) // bucket_seconds
                by_bucket[bucket].append(event)
        for offset in range(3):
            window_events = by_bucket.get(current_bucket - offset, [])
            if len(window_events) < MIN_WINDOW_QUERIES or not predicate(window_events):
                return False
        return True


def _window_p95(events: list[MapQueryEvent]) -> float:
    durations = sorted(event.duration_ms for event in events)
    return durations[max(0, ceil(len(durations) * 0.95) - 1)] if durations else 0.0


def _window_rate(events: list[MapQueryEvent], response_status: str) -> float:
    if not events:
        return 0.0
    return sum(event.response_status == response_status for event in events) / len(events)


def _window_cache_hit_rate(events: list[MapQueryEvent]) -> float:
    return sum(event.cache_hit for event in events) / len(events) if events else 0.0


map_query_cache = MapQueryCache()
map_performance_monitor = MapPerformanceMonitor()


def clear_map_query_cache() -> None:
    """Invalidate map results after a restaurant or photo mutation."""
    map_query_cache.clear()
