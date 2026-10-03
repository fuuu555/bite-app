"""Exploration service unit tests / 探索服務單元測試。"""

import uuid

import pytest

from api.domain.models import Restaurant
from api.domain.schemas import ExploreAppSignalsResponse, ExploreGoogleSignalsResponse
from api.services.ranking import (
    RankingSignals,
    StableRestaurantRanking,
    distance_score,
    rank_restaurants,
    recommendation_score,
    trust_score,
)


def test_stable_ranking_is_explicit_and_repeatable() -> None:
    """The skeleton order is deterministic and does not imply a recommendation score."""
    restaurants = [
        Restaurant(id=uuid.UUID(int=2), name="Beta", address="B"),
        Restaurant(id=uuid.UUID(int=3), name="alpha", address="C"),
        Restaurant(id=uuid.UUID(int=1), name="Alpha", address="A"),
    ]

    ranking = StableRestaurantRanking()
    first = ranking.rank(restaurants)
    second = ranking.rank(list(reversed(restaurants)))

    assert ranking.key == "stable"
    assert [item.id for item in first] == [uuid.UUID(int=1), uuid.UUID(int=3), uuid.UUID(int=2)]
    assert [item.id for item in second] == [item.id for item in first]


def test_recommendation_score_renormalizes_missing_signals() -> None:
    restaurant = Restaurant(
        id=uuid.UUID(int=10),
        name="Alpha",
        address="A",
        price_range="under_200",
    )
    score = recommendation_score(
        restaurant,
        RankingSignals(
            distance_meters=None,
            app=ExploreAppSignalsResponse(revisit_rate=100, rating_count=10),
            google=None,
        ),
        price_filter_active=False,
    )

    assert score == pytest.approx(100)


def test_recommendation_helpers_use_the_documented_v1_ranges() -> None:
    assert distance_score(0) == 100
    assert distance_score(5_000) == 50
    assert distance_score(10_000) == 0
    assert trust_score(1) == 25
    assert trust_score(3) == 60
    assert trust_score(10) == 100


def test_recommendation_sort_uses_app_and_google_signals() -> None:
    first = Restaurant(
        id=uuid.UUID(int=11),
        name="First",
        address="A",
        price_range="under_200",
    )
    second = Restaurant(
        id=uuid.UUID(int=12),
        name="Second",
        address="B",
        price_range="under_200",
    )
    ranked = rank_restaurants(
        [second, first],
        sort="recommended",
        distances={first.id: 100, second.id: 5_000},
        app_signals={
            first.id: ExploreAppSignalsResponse(revisit_rate=90, rating_count=10),
            second.id: ExploreAppSignalsResponse(revisit_rate=10, rating_count=1),
        },
        google_signals={
            first.id: ExploreGoogleSignalsResponse(rating=4.8, review_count=100),
            second.id: ExploreGoogleSignalsResponse(rating=3.0, review_count=100),
        },
        price_filter_active=False,
    )

    assert [item.id for item in ranked] == [first.id, second.id]
