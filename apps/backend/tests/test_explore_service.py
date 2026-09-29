"""Exploration service unit tests / 探索服務單元測試。"""

import uuid

from api.domain.models import Restaurant
from api.services.ranking import StableRestaurantRanking


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
