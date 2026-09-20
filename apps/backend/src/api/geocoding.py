"""Replaceable geocoding boundary / 可替換的地址定位邊界。"""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx

from api.config import get_settings
from api.schemas import GeocodingCandidate


class GeocodingProvider(Protocol):
    """Only providers whose licence permits storage may implement this interface.

    僅授權允許保存結果的 Provider 才能實作此介面。
    """

    @property
    def configured(self) -> bool: ...

    async def geocode(self, address: str) -> list[GeocodingCandidate]: ...

    async def reverse(self, latitude: float, longitude: float) -> str | None: ...


class UnconfiguredGeocodingProvider:
    @property
    def configured(self) -> bool:
        return False

    async def geocode(self, address: str) -> list[GeocodingCandidate]:
        del address
        return []

    async def reverse(self, latitude: float, longitude: float) -> str | None:
        del latitude, longitude
        return None


class NominatimGeocodingProvider:
    """OpenStreetMap Nominatim adapter / OpenStreetMap Nominatim 轉接器。"""

    endpoint = "https://nominatim.openstreetmap.org"

    @property
    def configured(self) -> bool:
        return True

    async def geocode(self, address: str) -> list[GeocodingCandidate]:
        # Taiwan addresses are commonly written as postal-code + city + road + number,
        # while Nominatim indexes them more reliably as number + road + administrative areas.
        # 台灣地址常寫成郵遞區號＋縣市＋道路＋門牌，但 Nominatim 對門牌＋道路＋行政區較容易命中。
        query = normalize_taiwan_address(address)
        data = await self._request("/search", {"q": query, "format": "jsonv2", "limit": 5})
        return [
            GeocodingCandidate(
                label=str(item.get("display_name", "")),
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
            )
            for item in data
            if item.get("display_name") and item.get("lat") and item.get("lon")
        ]

    async def reverse(self, latitude: float, longitude: float) -> str | None:
        data = await self._request(
            "/reverse",
            {"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 18},
        )
        label = data.get("display_name")
        return str(label) if label else None

    async def _request(
        self, path: str, params: dict[str, str | int | float]
    ) -> Any:
        settings = get_settings()
        headers = {"User-Agent": settings.geocoding_user_agent}
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            response = await client.get(f"{self.endpoint}{path}", params=params)
            response.raise_for_status()
            return response.json()


def get_geocoding_provider() -> GeocodingProvider:
    """Build the configured provider / 建立設定中的地址定位 Provider。"""
    provider = get_settings().geocoding_provider.lower()
    if provider == "nominatim":
        return NominatimGeocodingProvider()
    return UnconfiguredGeocodingProvider()


def normalize_taiwan_address(address: str) -> str:
    """Normalize common Taiwan address order for geocoding / 正規化台灣常見地址格式。"""
    normalized = re.sub(r"^\s*\d{3,6}\s*", "", address.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    number_match = re.search(r"(?P<number>\d{1,4})號", normalized)
    if number_match:
        before_number = normalized[: number_match.start()]
        separator_positions = [
            before_number.rfind(separator) for separator in ("里", "區", "市", "鄉", "鎮")
        ]
        separator_position = max(separator_positions)
        if separator_position >= 0:
            prefix = before_number[: separator_position + 1].strip(" ,")
            road = before_number[separator_position + 1 :].strip(" ,")
            number = number_match.group("number")
            suffix = normalized[number_match.end() :].strip(" ,")
            if road:
                parts = [f"{number}, {road}", prefix, suffix]
                return ", ".join(part for part in parts if part)
    return normalized
