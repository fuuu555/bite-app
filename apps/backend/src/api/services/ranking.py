"""Transparent restaurant ranking strategies / 可解釋的餐廳排序策略。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import inf
from uuid import UUID

from api.domain.models import Restaurant
from api.domain.schemas import (
    ExploreAppSignalsResponse,
    ExploreGoogleSignalsResponse,
    ExploreSort,
)


class RestaurantRanking:
    """Protocol-like boundary retained for the deterministic skeleton strategy."""

    key: ExploreSort

    def rank(self, restaurants: Sequence[Restaurant]) -> list[Restaurant]:
        raise NotImplementedError


class StableRestaurantRanking(RestaurantRanking):
    """Deterministic order used only for compatibility and explicit fallback."""

    key: ExploreSort = "stable"

    def rank(self, restaurants: Sequence[Restaurant]) -> list[Restaurant]:
        return sorted(restaurants, key=lambda item: (item.name.casefold(), str(item.id)))


stable_restaurant_ranking = StableRestaurantRanking()


@dataclass(frozen=True)
class RankingSignals:
    """Signals needed to rank one restaurant without exposing a score."""

    distance_meters: float | None
    app: ExploreAppSignalsResponse | None
    google: ExploreGoogleSignalsResponse | None


RECOMMENDATION_WEIGHTS: dict[str, float] = {
    "distance": 0.25,
    "revisit_rate": 0.30,
    "google_rating": 0.15,
    "trust": 0.15,
    "price": 0.15,
}


def trust_score(rating_count: int | None) -> float | None:
    """Convert the v1 App review-count proxy into a 0-100 score."""
    if rating_count is None or rating_count <= 0:
        return None
    if rating_count >= 10:
        return 100.0
    if rating_count >= 3:
        return 60.0
    return 25.0


def distance_score(distance_meters: float | None) -> float | None:
    """Linearly score 0m as 100 and 10km as 0, clamped to 0-100."""
    if distance_meters is None:
        return None
    return max(0.0, min(100.0, 100.0 - distance_meters / 100.0))


def google_rating_score(rating: float | None) -> float | None:
    if rating is None:
        return None
    return max(0.0, min(100.0, rating / 5.0 * 100.0))


def recommendation_score(
    restaurant: Restaurant,
    signals: RankingSignals,
    *,
    price_filter_active: bool,
) -> float | None:
    """Calculate a normalized weighted score using only available signals."""
    values: dict[str, float | None] = {
        "distance": distance_score(signals.distance_meters),
        "revisit_rate": signals.app.revisit_rate if signals.app else None,
        "google_rating": google_rating_score(signals.google.rating if signals.google else None),
        "trust": trust_score(signals.app.rating_count if signals.app else None),
        "price": 100.0 if price_filter_active and restaurant.price_range else None,
    }
    available = [
        (values[name], weight)
        for name, weight in RECOMMENDATION_WEIGHTS.items()
        if values[name] is not None
    ]
    if not available:
        return None
    return sum(value * weight for value, weight in available if value is not None) / sum(
        weight for _, weight in available
    )


def rank_restaurants(
    restaurants: Sequence[Restaurant],
    *,
    sort: ExploreSort,
    distances: Mapping[UUID, float | None],
    app_signals: Mapping[UUID, ExploreAppSignalsResponse],
    google_signals: Mapping[UUID, ExploreGoogleSignalsResponse | None],
    price_filter_active: bool,
) -> list[Restaurant]:
    """Rank restaurants using the selected public Explore sort mode."""
    if sort == "stable":
        return stable_restaurant_ranking.rank(restaurants)

    signal_by_id = {
        restaurant.id: RankingSignals(
            distance_meters=distances.get(restaurant.id),
            app=app_signals.get(restaurant.id),
            google=google_signals.get(restaurant.id),
        )
        for restaurant in restaurants
    }

    def key(restaurant: Restaurant) -> tuple[object, ...]:
        signals = signal_by_id[restaurant.id]
        app_revisit = signals.app.revisit_rate if signals.app else None
        google_rating = signals.google.rating if signals.google else None
        trust = trust_score(signals.app.rating_count if signals.app else None)
        distance = signals.distance_meters
        if sort == "recommended":
            score = recommendation_score(
                restaurant,
                signals,
                price_filter_active=price_filter_active,
            )
            return (
                _missing_last(score),
                _descending(score),
                _missing_last(app_revisit),
                _descending(app_revisit),
                _missing_last(google_rating),
                _descending(google_rating),
                _missing_last(distance),
                distance if distance is not None else inf,
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        if sort == "distance":
            return (
                _missing_last(distance),
                distance if distance is not None else inf,
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        if sort == "price":
            return (
                _price_rank(restaurant.price_range),
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        if sort == "revisit_rate":
            return (
                _missing_last(app_revisit),
                _descending(app_revisit),
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        if sort == "google_rating":
            return (
                _missing_last(google_rating),
                _descending(google_rating),
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        if sort == "trust":
            return (
                _missing_last(trust),
                _descending(trust),
                restaurant.name.casefold(),
                str(restaurant.id),
            )
        return (restaurant.name.casefold(), str(restaurant.id))

    return sorted(restaurants, key=key)


def _descending(value: float | None) -> float:
    return -(value if value is not None else 0.0)


def _missing_last(value: float | None) -> int:
    return 1 if value is None else 0


def _price_rank(price_range: str | None) -> int:
    if price_range is None:
        return 99
    return {
        "under_200": 0,
        "200_to_400": 1,
        "400_to_800": 2,
        "over_800": 3,
    }.get(price_range, 99)
