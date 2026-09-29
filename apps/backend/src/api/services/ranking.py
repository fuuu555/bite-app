"""Explicit restaurant ranking boundary / 明確的餐廳排序邊界。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from api.domain.models import Restaurant
from api.domain.schemas import ExploreSort


class RestaurantRanking(Protocol):
    """Interface for future product-approved ranking strategies / 排序策略介面。"""

    key: ExploreSort

    def rank(self, restaurants: Sequence[Restaurant]) -> list[Restaurant]: ...


class StableRestaurantRanking:
    """Deterministic skeleton order; this is not a recommendation score.

    依店名與 ID 提供可重現的骨架排序，不代表推薦分數。
    """

    key: ExploreSort = "stable"

    def rank(self, restaurants: Sequence[Restaurant]) -> list[Restaurant]:
        return sorted(restaurants, key=lambda item: (item.name.casefold(), str(item.id)))


stable_restaurant_ranking = StableRestaurantRanking()
